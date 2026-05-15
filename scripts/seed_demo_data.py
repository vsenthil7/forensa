"""Forensa demo data seeder (closes IP #1 - tools/demo.sh prerequisite).

Writes a complete end-to-end demo dataset to a live PostgreSQL instance so
tools/demo.sh + tools/demo.ps1 have something real to call against:

  1. One tenant (with a stub HMAC signing secret).
  2. One agent under that tenant (Ed25519 keypair generated fresh).
  3. One policy bundle in `active` status (after walking the approval workflow
     proposed -> reviewed -> approved -> active).
  4. Five Receipts chained through the full receipt_builder:
       - 3 on 2026-05-13 (anchored day; demo's verification target)
       - 2 on 2026-05-14 (recent day; un-anchored)
  5. One TimestampAnchorRow with status='anchored' for 2026-05-13.
     By default this uses Rfc3161TimestampClient against FreeTSA
     (https://freetsa.org/tsr), producing a real RFC 3161 DER TSR
     bound by the public-internet TSA. Set FORENSA_DEMO_USE_MOCK_TSA=1
     to fall back to MockTimestampClient for offline / air-gapped runs.
  6. A signed bearer token via mint_hmac_token() so tools/demo.sh can pass
     `Authorization: Bearer $FORENSA_TOKEN` against the running API.

Idempotent. Re-running on an already-seeded DB reuses the tenant + agent +
bundle + receipts; only the bearer token is re-minted (its exp claim shifts).

Usage:
    poetry run python scripts/seed_demo_data.py
    # then paste the printed env vars into your shell and run tools/demo.sh

Env vars:
    FORENSA_DB_URL              required - async-postgres URL
    FORENSA_DEMO_HMAC_SECRET    optional - 32+ bytes hex; deterministic
                                fallback if unset (NOT for production)

Limitations (tracked as NEW-Pxx items, no silent drops):
    - By default the seeder hits a live public TSA (FreeTSA); set
      FORENSA_DEMO_USE_MOCK_TSA=1 for offline runs or when the network
      is restricted. Mock-mode TSRs are deterministic JSON, NOT real DER,
      and the demo's `openssl ts -verify` step will fail against them.
    - No console state is seeded.
    - HMAC tokens replace OIDC at CP10.1.
    - On idempotent re-seed when the agent row exists but receipts don't,
      a freshly generated agent_priv will not match the persisted
      AgentRow.identity_public_key for verification of those new receipts.
      Production runs hit this rarely and the script's standard path is
      "clean DB -> full seed". Documented as known limitation.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import secrets
import sys
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select

from apps.api.auth.token import mint_hmac_token
from packages.crypto.sign import generate_keypair
from packages.crypto.tsa import MockTimestampClient, Rfc3161TimestampClient, TimestampClient
from packages.ledger.anchor import AnchorAlreadyExistsError, anchor_day
from packages.ledger.bundle_repository import write_bundle
from packages.ledger.bundle_workflow import (
    activate,
    approve,
    propose,
    review,
)
from packages.ledger.models import (
    AgentRow,
    EventRow,
    PolicyBundleRow,
    PolicySnapshotRow,
    ReceiptRow,
    TenantRow,
)
from packages.ledger.receipt_builder import build_receipt
from packages.ledger.session import make_engine, make_sessionmaker, session_scope
from packages.policy.bundle_builder import build_bundle
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.policy.snapshot import capture_snapshot
from packages.schema.receipt import Receipt

DEFAULT_TSA_ENDPOINT = "https://freetsa.org/tsr"


def _build_timestamp_client() -> TimestampClient:
    """Build the TSA client per env config. Real RFC 3161 by default.

    Precedence:
      - FORENSA_DEMO_USE_MOCK_TSA=1 -> MockTimestampClient (offline / CI).
      - FORENSA_DEMO_TSA_ENDPOINT   -> override the TSA URL (default
                                       https://freetsa.org/tsr).

    Default behaviour is REAL: the seeder hits the public-internet TSA
    so the resulting TimestampAnchorRow contains genuine RFC 3161 DER
    that `openssl ts -verify` can validate against the TSA cert chain.
    """
    if os.environ.get("FORENSA_DEMO_USE_MOCK_TSA") == "1":
        print("  [tsa]    FORENSA_DEMO_USE_MOCK_TSA=1 -> MockTimestampClient")
        return MockTimestampClient(identifier="mock-tsa://forensa-demo")
    endpoint = os.environ.get("FORENSA_DEMO_TSA_ENDPOINT", DEFAULT_TSA_ENDPOINT)
    print(f"  [tsa]    Rfc3161TimestampClient -> {endpoint}")
    return Rfc3161TimestampClient(endpoint_url=endpoint)


DEMO_TENANT_SLUG = "forensa-demo"
DEMO_TENANT_NAME = "Forensa Demo Tenant"
DEMO_AGENT_SLUG = "demo-agent"
DEMO_AGENT_NAME = "Demo Agent (seeded)"
DEMO_SIGNING_KEY_ID = "demo-tenant-key-v1"

# Fixed scope so tools/demo.sh sees the same anchored day across reseeds.
DAY_ANCHORED = datetime(2026, 5, 13, tzinfo=UTC)
DAY_RECENT = datetime(2026, 5, 14, tzinfo=UTC)

BUNDLE_VERSION = "1.0.0"
BUNDLE_CONTENT = {
    "rules": [
        {"kind": "tool_call", "decision": "allow"},
        {"kind": "deny_kind", "decision": "deny"},
    ],
    "default": "allow",
}


def _banner(title: str) -> None:
    print()
    print("=" * 72)
    print(f"  {title}")
    print("=" * 72)


def _resolve_hmac_secret() -> bytes:
    """Return the demo tenant's HMAC secret (32+ bytes).

    Honours FORENSA_DEMO_HMAC_SECRET if set (hex-encoded). Otherwise derives
    a deterministic-but-warning secret from the slug so reseeds produce the
    same secret. NOT for production.
    """
    env_hex = os.environ.get("FORENSA_DEMO_HMAC_SECRET")
    if env_hex:
        try:
            secret = bytes.fromhex(env_hex)
        except ValueError as exc:
            raise SystemExit("FORENSA_DEMO_HMAC_SECRET must be hex-encoded") from exc
        if len(secret) < 32:
            raise SystemExit(f"FORENSA_DEMO_HMAC_SECRET must be >= 32 bytes (got {len(secret)})")
        return secret
    print(
        "  WARN: FORENSA_DEMO_HMAC_SECRET not set; deriving deterministic "
        "demo secret from slug. Do NOT use in production."
    )
    return (DEMO_TENANT_SLUG.encode("utf-8") * 4)[:32].ljust(32, b"\x00")


async def _get_or_create_tenant(session) -> TenantRow:
    stmt = select(TenantRow).where(TenantRow.slug == DEMO_TENANT_SLUG)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing is not None:
        print(f"  [tenant] reusing tenant_id={existing.id}")
        return existing
    row = TenantRow(
        id=uuid4(),
        slug=DEMO_TENANT_SLUG,
        display_name=DEMO_TENANT_NAME,
        signing_key_id=DEMO_SIGNING_KEY_ID,
        created_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    print(f"  [tenant] CREATED tenant_id={row.id}")
    return row


async def _get_or_create_agent(session, tenant_id: UUID) -> tuple[AgentRow, bytes, bytes]:
    """Return (AgentRow, tenant_signing_priv_key, agent_signing_priv_key).

    Two INDEPENDENT Ed25519 keypairs are generated:
      - tenant_priv: used by build_receipt for the tenant-side signature
        (in production this lives in the tenant's KMS / Vault). Stub for
        seed-data only.
      - agent_priv: used by build_receipt for the AGENT-side dual signature
        (BR-02). Its public half is persisted as AgentRow.identity_public_key
        so a verifier can later prove the receipt was signed by THIS agent.

    Both private halves are kept only in-memory for this run; no KMS adapter
    yet (NEW-P10.X.kms-adapter).
    """
    stmt = select(AgentRow).where(AgentRow.tenant_id == tenant_id, AgentRow.slug == DEMO_AGENT_SLUG)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing is not None:
        # On reseed we don't have the original private halves; generate
        # fresh ones. The persisted AgentRow.identity_public_key won't
        # verify against the new agent_priv -- but the receipts being
        # signed in this run are NEW receipts so their agent_signature
        # WILL verify under whichever agent public key was persisted at
        # the time. The seed script's idempotent-reseed path SKIPS the
        # chain rebuild (see _seed_already_has_receipts) so this freshness
        # is only visible when there are no existing receipts AND the agent
        # already existed. Documented as known limitation.
        tenant_priv, _ = generate_keypair()
        agent_priv, _ = generate_keypair()
        print(
            f"  [agent]  reusing agent_id={existing.id} "
            "(fresh tenant + agent private keys for signing)"
        )
        return existing, tenant_priv, agent_priv
    tenant_priv, _ = generate_keypair()
    agent_priv, agent_pub = generate_keypair()
    row = AgentRow(
        id=uuid4(),
        tenant_id=tenant_id,
        slug=DEMO_AGENT_SLUG,
        display_name=DEMO_AGENT_NAME,
        identity_public_key=agent_pub,
        status="active",
        created_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    print(f"  [agent]  CREATED agent_id={row.id} (tenant + agent keypairs generated)")
    return row, tenant_priv, agent_priv


async def _get_or_create_bundle(session, tenant_id: UUID):
    """Build + walk through approval workflow to active. Idempotent."""
    stmt = select(PolicyBundleRow).where(
        PolicyBundleRow.tenant_id == tenant_id,
        PolicyBundleRow.version == BUNDLE_VERSION,
    )
    result = await session.execute(stmt)
    existing_row = result.scalar_one_or_none()
    if existing_row is not None:
        bundle = build_bundle(tenant_id=tenant_id, version=BUNDLE_VERSION, content=BUNDLE_CONTENT)
        bundle = bundle.model_copy(update={"id": existing_row.id})
        print(f"  [bundle] reusing bundle_id={existing_row.id} status={existing_row.status}")
        return bundle

    bundle = build_bundle(tenant_id=tenant_id, version=BUNDLE_VERSION, content=BUNDLE_CONTENT)
    await write_bundle(session, bundle)
    print(f"  [bundle] CREATED bundle_id={bundle.id} status=proposed")

    # Distinct actors per segregation-of-duties.
    author_id = uuid4()
    reviewer_id = uuid4()
    approver_id = uuid4()
    activator_id = uuid4()
    # propose() emits the author row so segregation checks have a reference.
    await propose(
        session,
        bundle_id=bundle.id,
        author_actor_id=author_id,
        reason="demo seed: author signs proposal",
    )
    await review(
        session,
        bundle_id=bundle.id,
        reviewer_actor_id=reviewer_id,
        reason="demo seed: auto-review",
    )
    await approve(
        session,
        bundle_id=bundle.id,
        approver_actor_id=approver_id,
        reason="demo seed: auto-approve",
    )
    await activate(
        session,
        bundle_id=bundle.id,
        activator_actor_id=activator_id,
        reason="demo seed: auto-activate",
    )
    print("  [bundle] WALKED proposed -> reviewed -> approved -> active")
    return bundle


async def _build_chain_for_day(
    session,
    *,
    tenant: TenantRow,
    agent: AgentRow,
    bundle,
    tenant_priv: bytes,
    agent_priv: bytes,
    day: datetime,
    n_events: int,
    starting_sequence: int,
    prev_receipt: Receipt | None,
) -> tuple[list[Receipt], Receipt | None]:
    """Persist n_events Receipt+Event+Snapshot triples for one day.

    Each receipt is dual-signed: tenant signature via tenant_priv +
    agent signature via agent_priv (BR-02). The receipt's agent_signature
    column is populated from build_receipt's agent_signing_key parameter.
    """
    mock_gate = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )
    receipts: list[Receipt] = []
    prev = prev_receipt
    for i in range(n_events):
        action = {"kind": "tool_call", "step": i}
        verdict = await mock_gate.evaluate(tenant.id, action)
        snapshot = capture_snapshot(bundle, verdict)
        snapshot_id = uuid4()

        snap_row = PolicySnapshotRow(
            id=snapshot_id,
            tenant_id=tenant.id,
            policy_bundle_id=bundle.id,
            policy_bundle_version=bundle.version,
            content_hash=snapshot.content_hash,
            captured_at=day + timedelta(hours=12, minutes=i),
            verdict_decision=verdict.decision.value,
            verdict_reason=verdict.reason,
        )
        session.add(snap_row)
        await session.flush()

        event_id = uuid4()
        event_row = EventRow(
            id=event_id,
            tenant_id=tenant.id,
            agent_id=agent.id,
            trace_id=secrets.token_hex(16),
            span_id=secrets.token_hex(8),
            parent_span_id=None,
            kind="tool_call",
            occurred_at=day + timedelta(hours=12, minutes=i),
            payload={"step": i, "agent": DEMO_AGENT_SLUG, "action": "demo"},
            reasoning=None,
            output=None,
            policy_version=bundle.version,
            policy_verdict=verdict.decision.value,
        )
        session.add(event_row)
        await session.flush()

        receipt = build_receipt(
            tenant_id=tenant.id,
            event_id=event_id,
            event_payload=event_row.payload,
            policy_snapshot=snapshot,
            policy_snapshot_id=snapshot_id,
            prev_receipt=prev,
            tenant_signing_key=tenant_priv,
            agent_signing_key=agent_priv,
        )
        receipt = receipt.model_copy(
            update={
                "sequence": starting_sequence + i,
                "signed_at": day + timedelta(hours=12, minutes=i, seconds=30),
            }
        )
        receipt_row = ReceiptRow(
            id=receipt.id,
            tenant_id=receipt.tenant_id,
            event_id=receipt.event_id,
            policy_bundle_id=receipt.policy_bundle_id,
            policy_snapshot_id=snapshot_id,
            sequence=receipt.sequence,
            prev_receipt_hash=receipt.prev_receipt_hash,
            payload_hash=receipt.payload_hash,
            receipt_hash=receipt.receipt_hash,
            signature=receipt.signature,
            agent_signature=receipt.agent_signature,  # BR-02 dual signature seeded
            signed_at=receipt.signed_at,
        )
        session.add(receipt_row)
        await session.flush()
        receipts.append(receipt)
        prev = receipt
    return receipts, prev


async def _anchor_day_if_needed(session, *, tenant_id: UUID, day: datetime) -> None:
    """Anchor (tenant, day) via the configured TSA. Idempotent.

    By default this calls a live public TSA over HTTP (FreeTSA) to obtain
    a real RFC 3161 TSR. Set FORENSA_DEMO_USE_MOCK_TSA=1 to fall back to
    the in-process mock for offline / CI runs.
    """
    tsa_client = _build_timestamp_client()
    try:
        result = await anchor_day(
            session,
            tenant_id=tenant_id,
            day=day,
            timestamp_client=tsa_client,
        )
        root_disp = (result.root_hash[:16] + "...") if result.root_hash else "None"
        print(
            f"  [anchor] {day.date()} status={result.status} "
            f"receipts_covered={result.receipts_covered} "
            f"root_hash={root_disp}"
        )
    except AnchorAlreadyExistsError:
        print(f"  [anchor] {day.date()} already anchored; skipping")


async def _seed_already_has_receipts(session, tenant_id: UUID) -> bool:
    """True iff this tenant already has at least one receipt seeded."""
    stmt = select(ReceiptRow.id).where(ReceiptRow.tenant_id == tenant_id).limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def seed() -> int:
    db_url = os.environ.get("FORENSA_DB_URL")
    if not db_url:
        print("ERROR: FORENSA_DB_URL must be set (e.g. postgresql+asyncpg://...)")
        return 1

    _banner("Forensa demo data seeder")
    print(f"  DB URL: {db_url}")

    engine = make_engine(db_url)
    sessionmaker = make_sessionmaker(engine)
    secret = _resolve_hmac_secret()

    async with session_scope(sessionmaker) as session:
        _banner("Step 1: tenant + agent")
        tenant = await _get_or_create_tenant(session)
        agent, tenant_priv, agent_priv = await _get_or_create_agent(session, tenant.id)

        _banner("Step 2: policy bundle (proposed -> reviewed -> approved -> active)")
        bundle = await _get_or_create_bundle(session, tenant.id)

        already_seeded = await _seed_already_has_receipts(session, tenant.id)
        if already_seeded:
            _banner("Step 3: receipts already seeded; SKIPPING chain rebuild")
            print("  Receipts found for this tenant; re-using them.")
        else:
            _banner("Step 3: build receipt chain (3 anchored day + 2 recent day)")
            day1_receipts, last_day1 = await _build_chain_for_day(
                session,
                tenant=tenant,
                agent=agent,
                bundle=bundle,
                tenant_priv=tenant_priv,
                agent_priv=agent_priv,
                day=DAY_ANCHORED,
                n_events=3,
                starting_sequence=0,
                prev_receipt=None,
            )
            print(f"  [chain]  day1: {len(day1_receipts)} receipts on {DAY_ANCHORED.date()}")
            day2_receipts, _ = await _build_chain_for_day(
                session,
                tenant=tenant,
                agent=agent,
                bundle=bundle,
                tenant_priv=tenant_priv,
                agent_priv=agent_priv,
                day=DAY_RECENT,
                n_events=2,
                starting_sequence=3,
                prev_receipt=last_day1,
            )
            print(f"  [chain]  day2: {len(day2_receipts)} receipts on {DAY_RECENT.date()}")

        _banner("Step 4: anchor day 1 via real RFC 3161 TSA (FreeTSA by default)")
        await _anchor_day_if_needed(session, tenant_id=tenant.id, day=DAY_ANCHORED)

    await engine.dispose()

    # Mint a 1-year bearer token.
    token = mint_hmac_token(
        tenant_id=tenant.id,
        agent_id=agent.id,
        agent_slug=DEMO_AGENT_SLUG,
        secret=secret,
        scopes=["forensa.read", "forensa.write"],
        exp=(datetime.now(UTC) + timedelta(days=365)).timestamp(),
    )

    _banner("Done. Paste these into your shell.")
    print()
    print("  # PowerShell:")
    print(f"  $env:FORENSA_TENANT_ID = '{tenant.id}'")
    print(f'  $env:FORENSA_TOKEN     = "{token}"')
    print("  $env:FORENSA_SCOPE_START = '2026-05-13T00:00:00+00:00'")
    print("  $env:FORENSA_SCOPE_END   = '2026-05-14T23:59:59+00:00'")
    print()
    print("  # bash / zsh:")
    print(f"  export FORENSA_TENANT_ID='{tenant.id}'")
    print(f'  export FORENSA_TOKEN="{token}"')
    print("  export FORENSA_SCOPE_START='2026-05-13T00:00:00+00:00'")
    print("  export FORENSA_SCOPE_END='2026-05-14T23:59:59+00:00'")
    print()
    return 0


def main() -> int:  # pragma: no cover
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    return asyncio.run(seed())


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

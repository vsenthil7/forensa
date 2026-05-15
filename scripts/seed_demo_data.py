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
  5. One TimestampAnchorRow with status='anchored' for 2026-05-13 via
     MockTimestampClient (deterministic JSON TSR, NOT real RFC 3161 DER).
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
    - MockTimestampClient returns deterministic JSON, NOT real RFC 3161 DER.
      The `openssl ts -verify` step in tools/demo.sh will fail against the
      mock. Real-TSA seed support is NEW-P11.X.real-tsa-in-seed-script.
    - No console state is seeded.
    - HMAC tokens replace OIDC at CP10.1.
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
from packages.crypto.tsa import MockTimestampClient
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


async def _get_or_create_agent(session, tenant_id: UUID) -> tuple[AgentRow, bytes]:
    """Return (AgentRow, tenant_signing_private_key_bytes).

    Both halves of the keypair are freshly generated; we keep the private
    half only in-memory for this run since there's no KMS adapter yet
    (NEW-P10.X.kms-adapter).
    """
    stmt = select(AgentRow).where(AgentRow.tenant_id == tenant_id, AgentRow.slug == DEMO_AGENT_SLUG)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing is not None:
        priv, _ = generate_keypair()
        print(f"  [agent]  reusing agent_id={existing.id} " "(fresh private key for signing)")
        return existing, priv
    priv, pub = generate_keypair()
    row = AgentRow(
        id=uuid4(),
        tenant_id=tenant_id,
        slug=DEMO_AGENT_SLUG,
        display_name=DEMO_AGENT_NAME,
        identity_public_key=pub,
        status="active",
        created_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    print(f"  [agent]  CREATED agent_id={row.id}")
    return row, priv


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
    day: datetime,
    n_events: int,
    starting_sequence: int,
    prev_receipt: Receipt | None,
) -> tuple[list[Receipt], Receipt | None]:
    """Persist n_events Receipt+Event+Snapshot triples for one day."""
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
            agent_signature=None,  # BR-02 dual signature not seeded; demo OK
            signed_at=receipt.signed_at,
        )
        session.add(receipt_row)
        await session.flush()
        receipts.append(receipt)
        prev = receipt
    return receipts, prev


async def _anchor_day_if_needed(session, *, tenant_id: UUID, day: datetime) -> None:
    """Anchor (tenant, day) via MockTimestampClient. Idempotent."""
    mock_tsa = MockTimestampClient(identifier="mock-tsa://forensa-demo")
    try:
        result = await anchor_day(
            session,
            tenant_id=tenant_id,
            day=day,
            timestamp_client=mock_tsa,
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
        agent, tenant_priv = await _get_or_create_agent(session, tenant.id)

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
                day=DAY_RECENT,
                n_events=2,
                starting_sequence=3,
                prev_receipt=last_day1,
            )
            print(f"  [chain]  day2: {len(day2_receipts)} receipts on {DAY_RECENT.date()}")

        _banner("Step 4: anchor day 1 via MockTimestampClient")
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

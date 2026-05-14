"""Forensa tabletop demo (CP8.1).

Runs the full ingest - chain - pack - pipeline
in-process with no Postgres or LLM key required. Prints judge-friendly
progress and a verifiability summary.

Run with: poetry run python scripts/demo_tabletop.py
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from packages.crypto.sign import generate_keypair
from packages.export.builder import build_evidence_pack, verify_evidence_pack
from packages.ledger.receipt_builder import build_receipt, recompute_receipt_hash
from packages.narrative.client import MockNarrativeClient
from packages.narrative.prompt import build_prompt, prompt_hash
from packages.policy.bundle_builder import build_bundle
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.policy.snapshot import capture_snapshot
from packages.schema.receipt import Receipt

DEMO_TENANT = UUID("00000000-1111-2222-3333-444444444444")
BUNDLE_CONTENT = {"rules": [{"kind": "tool_call", "decision": "allow"}], "default": "allow"}


def banner(title: str) -> None:
    print()
    print("=" * 64)
    print(f"  {title}")
    print("=" * 64)


async def run_demo(n_events: int = 5) -> None:
    banner("Forensa tabletop demo - end-to-end evidence chain")
    print(f"Tenant:  {DEMO_TENANT}")
    print(f"Events:  {n_events}")

    # 1. Bootstrap policy bundle and policy gate.
    banner("Step 1: bootstrap policy bundle + mock Lobster Trap gate")
    bundle = build_bundle(tenant_id=DEMO_TENANT, version="1.0.0", content=BUNDLE_CONTENT)
    policy_gate = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )
    verdict = await policy_gate.evaluate(DEMO_TENANT, {"kind": "tool_call"})
    snapshot = capture_snapshot(bundle, verdict)
    snapshot_id = uuid4()
    print(f"  policy_bundle_id     = {bundle.id}")
    print(f"  policy_bundle.version= {bundle.version}")
    print(f"  content_hash         = {bundle.content_hash}")
    print(f"  verdict              = {verdict.decision.value} ({verdict.reason})")

    # 2. Sign and chain N receipts.
    banner(f"Step 2: ingest {n_events} events; produce {n_events} signed receipts")
    priv, pub = generate_keypair()
    receipts_with_snaps: list[tuple[Receipt, UUID]] = []
    prev: Receipt | None = None
    base = datetime.now(UTC) - timedelta(minutes=n_events)
    for i in range(n_events):
        r = build_receipt(
            tenant_id=DEMO_TENANT,
            event_id=uuid4(),
            event_payload={"step": i, "agent": "demo-agent"},
            policy_snapshot=snapshot,
            policy_snapshot_id=snapshot_id,
            prev_receipt=prev,
            tenant_signing_key=priv,
        )
        r = r.model_copy(update={"signed_at": base + timedelta(minutes=i)})
        receipts_with_snaps.append((r, snapshot_id))
        recomputed = recompute_receipt_hash(r, snapshot_id)
        ok = recomputed == r.receipt_hash
        print(f"  seq={r.sequence}  receipt_hash={r.receipt_hash[:20]}...  " f"recompute_ok={ok}")
        prev = r

    # 3. Build evidence pack.
    banner("Step 3: assemble evidence pack (JSON-LD + PROV-O)")
    pack = build_evidence_pack(
        tenant_id=DEMO_TENANT,
        generated_at=datetime.now(UTC),
        scope_start=base - timedelta(seconds=1),
        scope_end=datetime.now(UTC),
        receipts_with_snapshots=receipts_with_snaps,
    )
    print(f"  pack.id              = {pack.header.pack_id}")
    print(f"  pack.root_hash       = {pack.root_hash}")
    print(f"  pack.receipts        = {len(pack.receipts)}")
    print(f"  pack.activities      = {len(pack.activities)}")
    pack_verifies = verify_evidence_pack(pack)
    print(f"  verify_evidence_pack = {pack_verifies}")

    # 4. Generate narrative.
    banner("Step 4: generate regulator-ready narrative")
    prompt = build_prompt(pack)
    p_hash = prompt_hash(prompt)
    nclient = MockNarrativeClient()
    nresult = await nclient.generate_narrative(prompt, max_tokens=512)
    print(f"  model_id             = {nresult.model_id}")
    print(f"  prompt_hash          = {p_hash}")
    print(f"  content_hash         = {nresult.content_hash}")
    print(f"  narrative excerpt    = {nresult.narrative_text[:80]}...")

    # 5. End-to-end verifiability check.
    banner("Step 5: 3-anchor verifiability chain")
    # 5a: root_hash recompute
    a1 = verify_evidence_pack(pack)
    # 5b: prompt rebuild and hash match
    a2 = prompt_hash(build_prompt(pack)) == p_hash
    # 5c: deterministic content_hash for same prompt + same model + same client
    rerun = await nclient.generate_narrative(prompt, max_tokens=512)
    a3 = rerun.content_hash == nresult.content_hash
    print(f"  pack.root_hash recomputes        = {a1}")
    print(f"  prompt rebuilds to same hash     = {a2}")
    print(f"  narrative content_hash stable    = {a3}")

    banner("Demo complete")
    if all([a1, a2, a3]):
        print("  ALL CHECKS PASSED. Chain verified end-to-end.")
    else:  # pragma: no cover
        print("  ONE OR MORE CHECKS FAILED.")
        raise SystemExit(1)


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(run_demo())

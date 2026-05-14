"""Forensa BR-09 in-process load test (CP8.2).

Drives N events through the receipt-chain + evidence-pack + narrative path,
measures throughput and verifies chain integrity at the end.

Run with: poetry run python scripts/load_test.py [N]
"""

from __future__ import annotations

import asyncio
import sys
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from packages.crypto.sign import generate_keypair
from packages.export.builder import build_evidence_pack, verify_evidence_pack
from packages.ledger.receipt_builder import build_receipt, recompute_receipt_hash
from packages.policy.bundle_builder import build_bundle
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.policy.snapshot import capture_snapshot
from packages.schema.receipt import Receipt

TENANT = UUID("11111111-2222-3333-4444-555555555555")
BUNDLE_CONTENT = {"rules": [{"kind": "tool_call", "decision": "allow"}], "default": "allow"}


async def run_load(n: int) -> tuple[float, bool, int, str]:
    """Run N events end-to-end. Returns (seconds, integrity_ok, pack_size, root_hash)."""
    bundle = build_bundle(tenant_id=TENANT, version="1.0.0", content=BUNDLE_CONTENT)
    gate = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )
    verdict = await gate.evaluate(TENANT, {"kind": "tool_call"})
    snapshot = capture_snapshot(bundle, verdict)
    snapshot_id = uuid4()
    priv, _ = generate_keypair()

    pairs: list[tuple[Receipt, UUID]] = []
    prev: Receipt | None = None
    base = datetime.now(UTC) - timedelta(minutes=n)

    start = time.perf_counter()
    for i in range(n):
        r = build_receipt(
            tenant_id=TENANT,
            event_id=uuid4(),
            event_payload={"step": i},
            policy_snapshot=snapshot,
            policy_snapshot_id=snapshot_id,
            prev_receipt=prev,
            tenant_signing_key=priv,
        )
        r = r.model_copy(update={"signed_at": base + timedelta(seconds=i)})
        pairs.append((r, snapshot_id))
        prev = r

    pack = build_evidence_pack(
        tenant_id=TENANT,
        generated_at=datetime.now(UTC),
        scope_start=base - timedelta(seconds=1),
        scope_end=datetime.now(UTC),
        receipts_with_snapshots=pairs,
    )
    integrity_chain = all(recompute_receipt_hash(r, sid) == r.receipt_hash for r, sid in pairs)
    integrity_pack = verify_evidence_pack(pack)
    elapsed = time.perf_counter() - start

    return elapsed, integrity_chain and integrity_pack, len(pack.receipts), pack.root_hash


async def main(n: int) -> None:
    print(f"BR-09 load test: {n} events end-to-end")
    print("-" * 64)
    elapsed, ok, pack_size, root_hash = await run_load(n)
    throughput = n / elapsed if elapsed > 0 else float("inf")
    print(f"events             = {n}")
    print(f"elapsed seconds    = {elapsed:.3f}")
    print(f"throughput / sec   = {throughput:.1f}")
    print(f"pack receipts      = {pack_size}")
    print(f"pack root_hash     = {root_hash}")
    print(f"chain + pack ok    = {ok}")
    print("-" * 64)
    if not ok:  # pragma: no cover
        print("INTEGRITY FAILED.")
        raise SystemExit(1)
    # BR-09: 1000 events must complete in under 60 seconds with integrity.
    if n >= 1000 and elapsed >= 60:  # pragma: no cover
        print(f"BR-09 BUDGET BREACHED: {elapsed:.3f}s > 60s for {n} events.")
        raise SystemExit(2)
    print("BR-09 budget honoured.")


if __name__ == "__main__":  # pragma: no cover
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    asyncio.run(main(n))

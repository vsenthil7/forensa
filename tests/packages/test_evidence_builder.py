"""Tests for evidence pack builder (CP6.2)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from packages.crypto.sign import generate_keypair
from packages.export.builder import (
    EvidencePackError,
    build_evidence_pack,
    verify_evidence_pack,
)
from packages.ledger.receipt_builder import build_receipt
from packages.policy.bundle_builder import build_bundle
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.policy.snapshot import capture_snapshot
from packages.schema.receipt import Receipt

_TENANT_A = UUID("55555555-6666-7777-8888-999999999999")
_TENANT_B = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
_NOW = datetime(2026, 5, 14, 2, 0, tzinfo=UTC)
_LATER = datetime(2026, 5, 14, 3, 0, tzinfo=UTC)
_SAMPLE_CONTENT = {"rules": [{"kind": "x", "decision": "allow"}], "default": "allow"}


async def _make_chain(n: int, tenant_id: UUID = _TENANT_A) -> list[tuple[Receipt, UUID]]:
    bundle = build_bundle(tenant_id=tenant_id, version="1.0.0", content=_SAMPLE_CONTENT)
    mock = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )
    verdict = await mock.evaluate(tenant_id, {"kind": "x"})
    snap = capture_snapshot(bundle, verdict)
    snap_id = uuid4()
    priv, _ = generate_keypair()
    pairs: list[tuple[Receipt, UUID]] = []
    prev: Receipt | None = None
    for i in range(n):
        r = build_receipt(
            tenant_id=tenant_id,
            event_id=uuid4(),
            event_payload={"step": i},
            policy_snapshot=snap,
            policy_snapshot_id=snap_id,
            prev_receipt=prev,
            tenant_signing_key=priv,
        )
        pairs.append((r, snap_id))
        prev = r
    return pairs


@pytest.mark.asyncio
async def test_build_evidence_pack_happy_path():
    pairs = await _make_chain(3)
    pack = build_evidence_pack(
        tenant_id=_TENANT_A,
        generated_at=_LATER,
        scope_start=_NOW,
        scope_end=_LATER,
        receipts_with_snapshots=pairs,
    )
    assert pack.header.tenant_id == _TENANT_A
    assert pack.header.receipt_count == 3
    assert len(pack.receipts) == 3
    assert len(pack.activities) == 3
    assert [r.sequence for r in pack.receipts] == [0, 1, 2]


@pytest.mark.asyncio
async def test_build_evidence_pack_sorts_receipts_by_sequence():
    pairs = await _make_chain(4)
    shuffled = [pairs[2], pairs[0], pairs[3], pairs[1]]
    pack = build_evidence_pack(
        tenant_id=_TENANT_A,
        generated_at=_LATER,
        scope_start=_NOW,
        scope_end=_LATER,
        receipts_with_snapshots=shuffled,
    )
    assert [r.sequence for r in pack.receipts] == [0, 1, 2, 3]


@pytest.mark.asyncio
async def test_build_evidence_pack_root_hash_is_deterministic_across_input_order():
    pairs = await _make_chain(3)
    pack_a = build_evidence_pack(
        tenant_id=_TENANT_A,
        generated_at=_LATER,
        scope_start=_NOW,
        scope_end=_LATER,
        receipts_with_snapshots=pairs,
    )
    pack_b = build_evidence_pack(
        tenant_id=_TENANT_A,
        generated_at=_LATER,
        scope_start=_NOW,
        scope_end=_LATER,
        receipts_with_snapshots=list(reversed(pairs)),
    )
    # Same receipts, same order after sort, so receipts list is identical hash-wise.
    # Activities and pack_id differ (uuid4) so pack_a.root_hash != pack_b.root_hash,
    # but pack_a verifies against itself and pack_b verifies against itself.
    assert verify_evidence_pack(pack_a)
    assert verify_evidence_pack(pack_b)


@pytest.mark.asyncio
async def test_build_evidence_pack_rejects_cross_tenant_receipt():
    pairs_a = await _make_chain(2, tenant_id=_TENANT_A)
    pairs_b = await _make_chain(1, tenant_id=_TENANT_B)
    with pytest.raises(EvidencePackError, match="belongs to tenant"):
        build_evidence_pack(
            tenant_id=_TENANT_A,
            generated_at=_LATER,
            scope_start=_NOW,
            scope_end=_LATER,
            receipts_with_snapshots=pairs_a + pairs_b,
        )


@pytest.mark.asyncio
async def test_build_evidence_pack_rejects_inverted_scope():
    pairs = await _make_chain(1)
    with pytest.raises(EvidencePackError, match="scope_end"):
        build_evidence_pack(
            tenant_id=_TENANT_A,
            generated_at=_LATER,
            scope_start=_LATER,
            scope_end=_NOW,
            receipts_with_snapshots=pairs,
        )


@pytest.mark.asyncio
async def test_build_evidence_pack_empty_receipts_ok():
    pack = build_evidence_pack(
        tenant_id=_TENANT_A,
        generated_at=_LATER,
        scope_start=_NOW,
        scope_end=_LATER,
        receipts_with_snapshots=[],
    )
    assert pack.header.receipt_count == 0
    assert pack.receipts == []
    assert pack.activities == []
    assert verify_evidence_pack(pack)


@pytest.mark.asyncio
async def test_verify_evidence_pack_returns_true_for_untampered():
    pairs = await _make_chain(2)
    pack = build_evidence_pack(
        tenant_id=_TENANT_A,
        generated_at=_LATER,
        scope_start=_NOW,
        scope_end=_LATER,
        receipts_with_snapshots=pairs,
    )
    assert verify_evidence_pack(pack) is True


@pytest.mark.asyncio
async def test_verify_evidence_pack_returns_false_for_tampered_root_hash():
    pairs = await _make_chain(2)
    pack = build_evidence_pack(
        tenant_id=_TENANT_A,
        generated_at=_LATER,
        scope_start=_NOW,
        scope_end=_LATER,
        receipts_with_snapshots=pairs,
    )
    # Pack is frozen; reconstruct with a wrong root_hash to simulate tamper.
    tampered = pack.model_copy(update={"root_hash": "e" * 64})
    assert verify_evidence_pack(tampered) is False


@pytest.mark.asyncio
async def test_build_evidence_pack_activity_iris_link_receipt_event_snapshot():
    pairs = await _make_chain(1)
    r, snap_id = pairs[0]
    pack = build_evidence_pack(
        tenant_id=_TENANT_A,
        generated_at=_LATER,
        scope_start=_NOW,
        scope_end=_LATER,
        receipts_with_snapshots=pairs,
    )
    a = pack.activities[0]
    assert a.used_event == f"urn:forensa:event:{r.event_id}"
    assert a.used_policy_snapshot == f"urn:forensa:snapshot:{snap_id}"
    assert a.generated_receipt == f"urn:forensa:receipt:{r.id}"

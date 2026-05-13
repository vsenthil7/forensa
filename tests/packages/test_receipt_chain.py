"""Tests for receipt-chain invariants (CP4.3 monotonicity + CP4.4 integrity).

CP4.3 covers the sequence monotonicity rule: per-tenant sequence numbers are
strictly increasing, starting at 0, with no gaps; cross-tenant chains are
independent. The DB-level uq_receipts_tenant_sequence UNIQUE constraint
(alembic 0001) backstops this; the builder layer must respect it pre-INSERT.

CP4.4 covers hash chain integrity: every receipt.prev_receipt_hash points at
the previous receipt.receipt_hash; recompute_receipt_hash reproduces the
stored hash; tampering with any field breaks the chain.
"""

from __future__ import annotations

import asyncio
from itertools import pairwise
from uuid import UUID, uuid4

import pytest

from packages.crypto.sign import generate_keypair
from packages.ledger.receipt_builder import (
    ReceiptChainError,
    build_receipt,
    recompute_receipt_hash,
)
from packages.policy.bundle_builder import build_bundle
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.policy.snapshot import capture_snapshot
from packages.schema.receipt import Receipt

_TENANT_A = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
_TENANT_B = UUID("11111111-2222-3333-4444-555555555555")
_SAMPLE_CONTENT = {"rules": [{"kind": "x", "decision": "allow"}], "default": "allow"}


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _setup(tenant_id: UUID):
    """Build a (signing_key, snapshot, policy_snapshot_id) triple for a tenant."""
    bundle = build_bundle(tenant_id=tenant_id, version="1.0.0", content=_SAMPLE_CONTENT)
    mock = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )
    verdict = _run(mock.evaluate(tenant_id, {"kind": "x"}))
    snap = capture_snapshot(bundle, verdict)
    priv, _ = generate_keypair()
    return priv, snap, uuid4()


def _build_chain(tenant_id: UUID, n: int) -> tuple[list[Receipt], UUID]:
    """Build a chain of n linked receipts for one tenant. Returns (chain, snap_id)."""
    priv, snap, snap_id = _setup(tenant_id)
    receipts: list[Receipt] = []
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
        receipts.append(r)
        prev = r
    return receipts, snap_id


# ========== CP4.3 sequence monotonicity ==========


def test_genesis_receipt_has_sequence_zero():
    priv, snap, snap_id = _setup(_TENANT_A)
    r = build_receipt(
        tenant_id=_TENANT_A,
        event_id=uuid4(),
        event_payload={"k": "v"},
        policy_snapshot=snap,
        policy_snapshot_id=snap_id,
        prev_receipt=None,
        tenant_signing_key=priv,
    )
    assert r.sequence == 0
    assert r.prev_receipt_hash is None


def test_linked_receipt_increments_sequence_by_exactly_one():
    chain, _ = _build_chain(_TENANT_A, 2)
    assert chain[0].sequence == 0
    assert chain[1].sequence == 1
    assert chain[1].sequence - chain[0].sequence == 1


@pytest.mark.parametrize("n", [1, 2, 3, 5, 10])
def test_chain_sequence_is_strictly_monotonic_and_gap_free(n: int):
    chain, _ = _build_chain(_TENANT_A, n)
    sequences = [r.sequence for r in chain]
    assert sequences == list(range(n))
    for prev, curr in pairwise(chain):
        assert curr.sequence > prev.sequence
        assert curr.sequence == prev.sequence + 1


def test_cross_tenant_sequences_are_independent():
    chain_a, _ = _build_chain(_TENANT_A, 3)
    chain_b, _ = _build_chain(_TENANT_B, 3)
    assert [r.sequence for r in chain_a] == [0, 1, 2]
    assert [r.sequence for r in chain_b] == [0, 1, 2]
    assert chain_a[0].tenant_id == _TENANT_A
    assert chain_b[0].tenant_id == _TENANT_B


def test_cannot_continue_chain_across_tenants():
    chain_a, _ = _build_chain(_TENANT_A, 1)
    priv_b, snap_b, snap_b_id = _setup(_TENANT_B)
    with pytest.raises(ReceiptChainError, match="tenant"):
        build_receipt(
            tenant_id=_TENANT_B,
            event_id=uuid4(),
            event_payload={"k": "v"},
            policy_snapshot=snap_b,
            policy_snapshot_id=snap_b_id,
            prev_receipt=chain_a[0],
            tenant_signing_key=priv_b,
        )


# ========== CP4.4 hash chain integrity ==========


@pytest.mark.parametrize("n", [2, 3, 5])
def test_each_receipt_prev_hash_points_at_previous_receipt_hash(n: int):
    chain, _ = _build_chain(_TENANT_A, n)
    assert chain[0].prev_receipt_hash is None
    for prev, curr in pairwise(chain):
        assert curr.prev_receipt_hash == prev.receipt_hash


@pytest.mark.parametrize("n", [1, 3, 5])
def test_recompute_receipt_hash_matches_stored_for_full_chain(n: int):
    chain, snap_id = _build_chain(_TENANT_A, n)
    for r in chain:
        recomputed = recompute_receipt_hash(r, snap_id)
        assert recomputed == r.receipt_hash


def test_recompute_with_wrong_snapshot_id_does_not_match():
    chain, _ = _build_chain(_TENANT_A, 1)
    wrong_snap_id = uuid4()
    recomputed = recompute_receipt_hash(chain[0], wrong_snap_id)
    assert recomputed != chain[0].receipt_hash


def test_tampering_with_prev_receipt_hash_breaks_chain_linkage():
    chain, _ = _build_chain(_TENANT_A, 3)
    # If we mutate chain[1].prev_receipt_hash, it no longer matches chain[0].receipt_hash.
    # Receipt is frozen, so reconstruct via model_copy with override.
    tampered = chain[1].model_copy(update={"prev_receipt_hash": "a" * 64})
    assert tampered.prev_receipt_hash != chain[0].receipt_hash
    assert chain[1].prev_receipt_hash == chain[0].receipt_hash  # original intact


def test_chain_integrity_holds_under_long_chain():
    chain, snap_id = _build_chain(_TENANT_A, 20)
    # Every link verifies; no gaps.
    for prev, curr in pairwise(chain):
        assert curr.prev_receipt_hash == prev.receipt_hash
        assert curr.sequence == prev.sequence + 1
    # Every hash recomputes.
    for r in chain:
        assert recompute_receipt_hash(r, snap_id) == r.receipt_hash

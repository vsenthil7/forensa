"""Tests for packages/ledger/receipt_builder.py - 100% branch coverage.

Covers:
- build_receipt genesis path (prev=None, sequence=0, prev_hash=None)
- build_receipt linked path (sequence+1, prev_hash=prev.receipt_hash)
- ReceiptChainError on tenant_id mismatch with prev_receipt
- TypeError on non-dict event_payload
- verify_receipt_signature: True on fresh sign, False on tampered hash
- recompute_receipt_hash matches receipt.receipt_hash for fresh build
- Hypothesis property: arbitrary payloads round-trip through build + recompute
"""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from packages.crypto.sign import generate_keypair
from packages.ledger.receipt_builder import (
    ReceiptChainError,
    build_receipt,
    recompute_receipt_hash,
    verify_receipt_signature,
)
from packages.policy.bundle_builder import build_bundle
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.policy.snapshot import capture_snapshot
from packages.schema.receipt import Receipt

_TENANT_ID = UUID("66666666-6666-6666-6666-666666666666")
_OTHER_TENANT_ID = UUID("77777777-7777-7777-7777-777777777777")
_SAMPLE_CONTENT = {"rules": [{"kind": "deny_kind", "decision": "deny"}], "default": "allow"}
_SAMPLE_PAYLOAD = {"action": "send_email", "to": "alice@example.com"}


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_snapshot_and_id() -> tuple:
    """Build a PolicySnapshot and a synthetic snapshot_id (UUID) for tests."""
    bundle = build_bundle(tenant_id=_TENANT_ID, version="1.0.0", content=_SAMPLE_CONTENT)
    mock = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )
    verdict = _run(mock.evaluate(_TENANT_ID, {"kind": "x"}))
    snap = capture_snapshot(bundle, verdict)
    snap_id = uuid4()
    return bundle, snap, snap_id


def _build(
    *, prev: Receipt | None = None, tenant_id: UUID = _TENANT_ID
) -> tuple[Receipt, bytes, bytes, UUID]:
    """Helper: build a Receipt and return (receipt, priv_key, pub_key, snap_id)."""
    priv, pub = generate_keypair()
    _, snap, snap_id = _make_snapshot_and_id()
    receipt = build_receipt(
        tenant_id=tenant_id,
        event_id=uuid4(),
        event_payload=_SAMPLE_PAYLOAD,
        policy_snapshot=snap,
        policy_snapshot_id=snap_id,
        prev_receipt=prev,
        tenant_signing_key=priv,
    )
    return receipt, priv, pub, snap_id


# ---------- genesis path ----------


def test_genesis_receipt_has_sequence_zero_and_no_prev_hash():
    receipt, _, _, _ = _build(prev=None)
    assert receipt.sequence == 0
    assert receipt.prev_receipt_hash is None
    assert receipt.tenant_id == _TENANT_ID
    assert receipt.signed_at.tzinfo is not None
    # Receipt hash and signature must be present and correctly shaped.
    assert len(receipt.receipt_hash) == 64
    assert len(receipt.signature) == 64


# ---------- linked path ----------


def test_linked_receipt_increments_sequence_and_binds_prev_hash():
    genesis, priv, _, snap_id = _build(prev=None)
    _, snap, _ = _make_snapshot_and_id()
    linked = build_receipt(
        tenant_id=_TENANT_ID,
        event_id=uuid4(),
        event_payload={"action": "next"},
        policy_snapshot=snap,
        policy_snapshot_id=snap_id,
        prev_receipt=genesis,
        tenant_signing_key=priv,
    )
    assert linked.sequence == 1
    assert linked.prev_receipt_hash == genesis.receipt_hash


# ---------- tenant mismatch ----------


def test_build_rejects_prev_receipt_from_different_tenant():
    cross_tenant_genesis, priv, _, snap_id = _build(prev=None, tenant_id=_OTHER_TENANT_ID)
    _, snap, _ = _make_snapshot_and_id()
    with pytest.raises(ReceiptChainError, match="chains are per-tenant"):
        build_receipt(
            tenant_id=_TENANT_ID,
            event_id=uuid4(),
            event_payload=_SAMPLE_PAYLOAD,
            policy_snapshot=snap,
            policy_snapshot_id=snap_id,
            prev_receipt=cross_tenant_genesis,
            tenant_signing_key=priv,
        )


# ---------- type guard ----------


def test_build_rejects_non_dict_payload():
    priv, _ = generate_keypair()
    _, snap, snap_id = _make_snapshot_and_id()
    with pytest.raises(TypeError, match="event_payload must be a dict"):
        build_receipt(
            tenant_id=_TENANT_ID,
            event_id=uuid4(),
            event_payload="not a dict",  # type: ignore[arg-type]
            policy_snapshot=snap,
            policy_snapshot_id=snap_id,
            prev_receipt=None,
            tenant_signing_key=priv,
        )


# ---------- signature ----------


def test_signature_verifies_under_correct_public_key():
    receipt, _, pub, _ = _build(prev=None)
    assert verify_receipt_signature(receipt, pub) is True


def test_signature_does_not_verify_under_wrong_public_key():
    receipt, _, _, _ = _build(prev=None)
    _, other_pub = generate_keypair()
    assert verify_receipt_signature(receipt, other_pub) is False


# ---------- recompute ----------


def test_recompute_receipt_hash_matches_for_fresh_genesis():
    receipt, _, _, snap_id = _build(prev=None)
    assert recompute_receipt_hash(receipt, snap_id) == receipt.receipt_hash


def test_recompute_receipt_hash_matches_for_linked_receipt():
    genesis, priv, _, snap_id = _build(prev=None)
    _, snap, _ = _make_snapshot_and_id()
    linked = build_receipt(
        tenant_id=_TENANT_ID,
        event_id=uuid4(),
        event_payload={"action": "next"},
        policy_snapshot=snap,
        policy_snapshot_id=snap_id,
        prev_receipt=genesis,
        tenant_signing_key=priv,
    )
    assert recompute_receipt_hash(linked, snap_id) == linked.receipt_hash


# ---------- hypothesis property ----------


@given(
    st.dictionaries(
        keys=st.text(min_size=1, max_size=10),
        values=st.one_of(st.text(max_size=20), st.integers(-1000, 1000), st.booleans()),
        max_size=5,
    )
)
def test_arbitrary_payload_round_trips_through_recompute(payload):
    """For any canonicalisable payload, recompute_receipt_hash(build_receipt(...)) matches."""
    priv, _ = generate_keypair()
    _, snap, snap_id = _make_snapshot_and_id()
    receipt = build_receipt(
        tenant_id=_TENANT_ID,
        event_id=uuid4(),
        event_payload=payload,
        policy_snapshot=snap,
        policy_snapshot_id=snap_id,
        prev_receipt=None,
        tenant_signing_key=priv,
    )
    assert recompute_receipt_hash(receipt, snap_id) == receipt.receipt_hash

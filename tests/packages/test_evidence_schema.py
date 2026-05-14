"""Tests for evidence pack Pydantic schema (CP6.1)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from packages.export.schema import (
    JSONLD_CONTEXT,
    EvidencePack,
    EvidencePackHeader,
    ProvActivity,
    ReceiptEvidenceItem,
)

_NOW = datetime(2026, 5, 14, 2, 0, tzinfo=UTC)


def _header(**over):
    base = dict(
        pack_id=uuid4(),
        tenant_id=uuid4(),
        generated_at=_NOW,
        scope_start=_NOW,
        scope_end=_NOW,
        receipt_count=0,
    )
    base.update(over)
    return EvidencePackHeader(**base)


def _item(seq: int = 0, **over):
    base = dict(
        id=uuid4(),
        tenant_id=uuid4(),
        event_id=uuid4(),
        policy_bundle_id=uuid4(),
        policy_snapshot_id=uuid4(),
        sequence=seq,
        prev_receipt_hash=None if seq == 0 else "a" * 64,
        payload_hash="b" * 64,
        receipt_hash="c" * 64,
        signature_b64="AAAA",
        signed_at=_NOW,
    )
    base.update(over)
    return ReceiptEvidenceItem(**base)


def _activity(**over):
    base = dict(
        id="urn:forensa:activity:abc",
        used_event="urn:forensa:event:xyz",
        used_policy_snapshot="urn:forensa:snapshot:pqr",
        generated_receipt="urn:forensa:receipt:rst",
        started_at=_NOW,
        ended_at=_NOW,
    )
    base.update(over)
    return ProvActivity(**base)


# ===== EvidencePackHeader =====


def test_header_happy_path():
    h = _header()
    assert h.receipt_count == 0
    assert h.generated_at.tzinfo is not None


def test_header_rejects_naive_datetime():
    with pytest.raises(ValidationError, match="timezone-aware"):
        _header(generated_at=datetime(2026, 1, 1))


def test_header_rejects_negative_count():
    with pytest.raises(ValidationError):
        _header(receipt_count=-1)


def test_header_is_frozen():
    h = _header()
    with pytest.raises(ValidationError):
        h.receipt_count = 99  # type: ignore[misc]


# ===== ReceiptEvidenceItem =====


def test_item_happy_path():
    it = _item(seq=1)
    assert it.sequence == 1
    assert it.prev_receipt_hash == "a" * 64


def test_item_rejects_short_hash():
    with pytest.raises(ValidationError):
        _item(payload_hash="b" * 32)


def test_item_rejects_non_hex_hash():
    with pytest.raises(ValidationError, match="lowercase hex"):
        _item(receipt_hash="Z" * 64)


def test_item_rejects_naive_signed_at():
    with pytest.raises(ValidationError, match="timezone-aware"):
        _item(signed_at=datetime(2026, 1, 1))


def test_item_genesis_allows_null_prev_hash():
    it = _item(seq=0)
    assert it.prev_receipt_hash is None


# ===== ProvActivity =====


def test_activity_happy_path():
    a = _activity()
    assert a.activity_type == "prov:Activity"


def test_activity_rejects_naive_timestamp():
    with pytest.raises(ValidationError, match="timezone-aware"):
        _activity(started_at=datetime(2026, 1, 1))


# ===== EvidencePack =====


def test_pack_happy_path():
    p = EvidencePack(
        header=_header(receipt_count=2),
        receipts=[_item(seq=0), _item(seq=1)],
        activities=[_activity(), _activity()],
        root_hash="d" * 64,
    )
    assert p.context == JSONLD_CONTEXT
    assert p.pack_type == "forensa:EvidencePack"
    assert len(p.receipts) == 2


def test_pack_serialises_with_jsonld_aliases():
    p = EvidencePack(
        header=_header(),
        receipts=[],
        activities=[],
        root_hash="d" * 64,
    )
    dumped = p.model_dump(by_alias=True, mode="json")
    assert "@context" in dumped
    assert "@type" in dumped
    assert dumped["@context"] == JSONLD_CONTEXT


def test_pack_rejects_unsorted_receipts():
    with pytest.raises(ValidationError, match="sorted by sequence ASC"):
        EvidencePack(
            header=_header(receipt_count=2),
            receipts=[_item(seq=1), _item(seq=0)],  # reversed
            activities=[_activity(), _activity()],
            root_hash="d" * 64,
        )


def test_pack_rejects_non_hex_root_hash():
    with pytest.raises(ValidationError, match="lowercase hex"):
        EvidencePack(
            header=_header(),
            receipts=[],
            activities=[],
            root_hash="Z" * 64,
        )


def test_pack_empty_receipts_ok():
    p = EvidencePack(
        header=_header(),
        receipts=[],
        activities=[],
        root_hash="d" * 64,
    )
    assert p.receipts == []

"""Tests for Receipt schema model — 100% branch coverage."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from packages.schema.receipt import Receipt


_GOOD_HASH = "a" * 64
_GOOD_SIG = b"\x01" * 64


def _good(**over):
    base = dict(
        tenant_id=uuid4(),
        event_id=uuid4(),
        policy_bundle_id=uuid4(),
        sequence=0,
        payload_hash=_GOOD_HASH,
        receipt_hash="b" * 64,
        signature=_GOOD_SIG,
        signed_at=datetime(2026, 5, 13, 8, 0, tzinfo=timezone.utc),
    )
    base.update(over)
    return base


def test_receipt_minimal_valid():
    r = Receipt(**_good())
    assert r.sequence == 0
    assert r.prev_receipt_hash is None
    assert r.payload_hash == _GOOD_HASH
    assert r.receipt_hash == "b" * 64
    assert r.signature == _GOOD_SIG


def test_receipt_with_prev_hash():
    r = Receipt(prev_receipt_hash="c" * 64, **_good(sequence=1))
    assert r.prev_receipt_hash == "c" * 64
    assert r.sequence == 1


def test_receipt_explicit_id():
    rid = uuid4()
    r = Receipt(id=rid, **_good())
    assert r.id == rid


@pytest.mark.parametrize("seq", [0, 1, 100, 999999999])
def test_receipt_accepts_valid_sequence(seq):
    r = Receipt(**_good(sequence=seq))
    assert r.sequence == seq


@pytest.mark.parametrize("bad_seq", [-1, -100])
def test_receipt_rejects_negative_sequence(bad_seq):
    with pytest.raises(ValidationError):
        Receipt(**_good(sequence=bad_seq))


@pytest.mark.parametrize(
    "bad_prev",
    ["", "c" * 63, "c" * 65, "C" * 64, "g" * 64, "z" * 64],
)
def test_receipt_rejects_bad_prev_receipt_hash(bad_prev):
    with pytest.raises(ValidationError) as exc:
        Receipt(prev_receipt_hash=bad_prev, **_good())
    assert "64-char" in str(exc.value) or "hex" in str(exc.value)


def test_receipt_accepts_none_prev_receipt_hash():
    r = Receipt(prev_receipt_hash=None, **_good())
    assert r.prev_receipt_hash is None


@pytest.mark.parametrize(
    "bad_payload",
    ["", "a" * 63, "a" * 65, "A" * 64, "g" * 64],
)
def test_receipt_rejects_bad_payload_hash(bad_payload):
    with pytest.raises(ValidationError):
        Receipt(**_good(payload_hash=bad_payload))


@pytest.mark.parametrize(
    "bad_receipt",
    ["", "b" * 63, "b" * 65, "B" * 64, "g" * 64],
)
def test_receipt_rejects_bad_receipt_hash(bad_receipt):
    with pytest.raises(ValidationError):
        Receipt(**_good(receipt_hash=bad_receipt))


@pytest.mark.parametrize("bad_len", [0, 1, 32, 63, 65, 128])
def test_receipt_rejects_wrong_signature_length(bad_len):
    with pytest.raises(ValidationError) as exc:
        Receipt(**_good(signature=b"\x02" * bad_len))
    assert "64 bytes" in str(exc.value)


def test_receipt_rejects_naive_signed_at():
    with pytest.raises(ValidationError) as exc:
        Receipt(**_good(signed_at=datetime(2026, 5, 13, 8, 0)))
    assert "timezone-aware" in str(exc.value)


def test_receipt_frozen():
    r = Receipt(**_good())
    with pytest.raises(ValidationError):
        r.sequence = 99


def test_receipt_forbids_extra_fields():
    with pytest.raises(ValidationError):
        Receipt(evil="data", **_good())


def test_receipt_id_defaults_unique():
    r1 = Receipt(**_good())
    r2 = Receipt(**_good())
    assert r1.id != r2.id

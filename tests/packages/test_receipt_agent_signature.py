"""Tests for Receipt.agent_signature field (CP9.18 / BR-02 dual signature).

Covers the new optional ``agent_signature`` field on the Receipt schema:

- Construction with and without agent_signature.
- Validation of agent_signature length (64 bytes Ed25519).
- None remains permitted (backwards-compat for pre-CP9.18 receipts).
- The agent_signature is independent of the tenant signature (tenant
  signature continues to be required).
- frozen=True forbids post-construction mutation of agent_signature too.
"""

from __future__ import annotations

import dataclasses  # noqa: F401  (imported for symmetry with other test files)
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from packages.schema.receipt import Receipt

_GOOD_HASH = "a" * 64
_GOOD_SIG = b"\x01" * 64
_GOOD_AGENT_SIG = b"\x02" * 64


def _good(**over):
    base = dict(
        tenant_id=uuid4(),
        event_id=uuid4(),
        policy_bundle_id=uuid4(),
        sequence=0,
        payload_hash=_GOOD_HASH,
        receipt_hash="b" * 64,
        signature=_GOOD_SIG,
        signed_at=datetime(2026, 5, 14, 22, 30, tzinfo=UTC),
    )
    base.update(over)
    return base


def test_receipt_without_agent_signature_is_backwards_compatible():
    """Receipts persisted before CP9.18 have no agent_signature; permitted."""
    r = Receipt(**_good())
    assert r.agent_signature is None


def test_receipt_with_explicit_none_agent_signature():
    r = Receipt(agent_signature=None, **_good())
    assert r.agent_signature is None


def test_receipt_with_valid_agent_signature():
    r = Receipt(agent_signature=_GOOD_AGENT_SIG, **_good())
    assert r.agent_signature == _GOOD_AGENT_SIG
    # Tenant signature is still required and independent.
    assert r.signature == _GOOD_SIG


def test_receipt_agent_and_tenant_signatures_are_distinct():
    """The two signature fields hold independent bytes; one is not derived
    from the other."""
    r = Receipt(agent_signature=_GOOD_AGENT_SIG, **_good())
    assert r.signature != r.agent_signature
    assert len(r.signature) == 64
    assert len(r.agent_signature) == 64


@pytest.mark.parametrize(
    "bad_sig",
    [
        b"\x01" * 32,  # too short (32 bytes - half)
        b"\x01" * 63,  # one byte short
        b"\x01" * 65,  # one byte over
        b"\x01" * 96,  # too long (some Ed448 sigs are 114)
        b"",  # empty
    ],
)
def test_receipt_rejects_wrong_length_agent_signature(bad_sig):
    with pytest.raises(ValidationError) as ei:
        Receipt(agent_signature=bad_sig, **_good())
    assert "agent_signature" in str(ei.value)


def test_receipt_frozen_blocks_agent_signature_mutation():
    """Receipt is frozen; agent_signature must be immutable like every other field."""
    r = Receipt(agent_signature=_GOOD_AGENT_SIG, **_good())
    with pytest.raises(ValidationError):
        r.agent_signature = b"\x99" * 64  # type: ignore[misc]


def test_receipt_extra_forbid_still_holds_with_agent_signature_field():
    """Adding a new known field doesn't relax extra='forbid' on the model."""
    with pytest.raises(ValidationError):
        Receipt(agent_signature=_GOOD_AGENT_SIG, evil="data", **_good())


def test_receipt_serialises_agent_signature_as_bytes():
    """model_dump in python-mode keeps bytes; in JSON-mode it base64-encodes."""
    r = Receipt(agent_signature=_GOOD_AGENT_SIG, **_good())
    py = r.model_dump()
    assert py["agent_signature"] == _GOOD_AGENT_SIG
    js = r.model_dump(mode="json")
    # In JSON mode, bytes round-trip as base64; the field is present and not None.
    assert js["agent_signature"] is not None


def test_receipt_serialises_none_agent_signature_as_null():
    r = Receipt(**_good())
    py = r.model_dump()
    assert py["agent_signature"] is None
    js = r.model_dump(mode="json")
    assert js["agent_signature"] is None

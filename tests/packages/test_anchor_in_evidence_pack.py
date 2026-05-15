"""Tests for AnchorEvidence integration into EvidencePack (CP9.23).

The optional anchor field is bound into root_hash so any tamper of the
anchor data invalidates the pack. These tests exercise both the
anchored-row path and the deferred-tombstone path.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from packages.crypto.sign import generate_keypair
from packages.export.builder import build_evidence_pack, verify_evidence_pack
from packages.export.schema import AnchorEvidence
from packages.ledger.receipt_builder import build_receipt
from packages.policy.bundle_builder import build_bundle
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.policy.snapshot import capture_snapshot
from packages.schema.receipt import Receipt

_TENANT = UUID("55555555-6666-7777-8888-999999999999")
_NOW = datetime(2026, 5, 15, 6, 30, tzinfo=UTC)
_LATER = datetime(2026, 5, 15, 7, 30, tzinfo=UTC)
_GEN = datetime(2026, 5, 15, 7, 0, tzinfo=UTC)
_CONTENT = {"rules": [{"kind": "x", "decision": "allow"}], "default": "allow"}


async def _make_chain(n: int) -> list[tuple[Receipt, UUID]]:
    bundle = build_bundle(tenant_id=_TENANT, version="1.0.0", content=_CONTENT)
    mock = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )
    verdict = await mock.evaluate(_TENANT, {"kind": "x"})
    snap = capture_snapshot(bundle, verdict)
    snap_id = uuid4()
    priv, _ = generate_keypair()
    pairs: list[tuple[Receipt, UUID]] = []
    prev: Receipt | None = None
    for i in range(n):
        r = build_receipt(
            tenant_id=_TENANT,
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


def _anchored() -> AnchorEvidence:
    return AnchorEvidence(
        anchor_id=uuid4(),
        anchor_date=datetime(2026, 5, 15, tzinfo=UTC),
        status="anchored",
        root_hash="a" * 64,
        tsa_identifier="mock-tsa",
        tsr_bytes_b64=base64.b64encode(b"\x00\x01\x02").decode("ascii"),
        tsa_signature_b64=base64.b64encode(b"\xff" * 32).decode("ascii"),
        timestamped_at=datetime(2026, 5, 15, 6, 0, tzinfo=UTC),
        anchored_at=datetime(2026, 5, 15, 6, 5, tzinfo=UTC),
    )


def _deferred() -> AnchorEvidence:
    return AnchorEvidence(
        anchor_id=uuid4(),
        anchor_date=datetime(2026, 5, 15, tzinfo=UTC),
        status="deferred",
        root_hash=None,
        tsa_identifier="mock-tsa",
        tsr_bytes_b64=None,
        tsa_signature_b64=None,
        timestamped_at=None,
        anchored_at=datetime(2026, 5, 15, 6, 5, tzinfo=UTC),
    )


# ---------- AnchorEvidence schema validation ----------


def test_anchor_evidence_anchored_round_trip() -> None:
    a = _anchored()
    # extra="forbid" + frozen=True means model_dump round-trip is lossless.
    d = a.model_dump(mode="json")
    rebuilt = AnchorEvidence(**d)
    assert rebuilt == a


def test_anchor_evidence_deferred_round_trip() -> None:
    a = _deferred()
    d = a.model_dump(mode="json")
    rebuilt = AnchorEvidence(**d)
    assert rebuilt == a


def test_anchor_evidence_rejects_naive_anchored_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        AnchorEvidence(
            anchor_id=uuid4(),
            anchor_date=datetime(2026, 5, 15, tzinfo=UTC),
            status="anchored",
            root_hash="a" * 64,
            tsa_identifier="mock-tsa",
            tsr_bytes_b64="AAEC",
            tsa_signature_b64="//8=",
            timestamped_at=datetime(2026, 5, 15, 6, 0, tzinfo=UTC),
            anchored_at=datetime(2026, 5, 15, 6, 5),  # naive
        )


def test_anchor_evidence_rejects_naive_timestamped_at_when_present() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        AnchorEvidence(
            anchor_id=uuid4(),
            anchor_date=datetime(2026, 5, 15, tzinfo=UTC),
            status="anchored",
            root_hash="a" * 64,
            tsa_identifier="mock-tsa",
            tsr_bytes_b64="AAEC",
            tsa_signature_b64="//8=",
            timestamped_at=datetime(2026, 5, 15, 6, 0),  # naive
            anchored_at=datetime(2026, 5, 15, 6, 5, tzinfo=UTC),
        )


def test_anchor_evidence_accepts_none_timestamped_at() -> None:
    a = _deferred()
    assert a.timestamped_at is None


def test_anchor_evidence_rejects_bad_root_hash_length() -> None:
    with pytest.raises(ValueError, match="64 hex"):
        AnchorEvidence(
            anchor_id=uuid4(),
            anchor_date=datetime(2026, 5, 15, tzinfo=UTC),
            status="anchored",
            root_hash="abc",  # too short
            tsa_identifier="mock-tsa",
            tsr_bytes_b64="AAEC",
            tsa_signature_b64="//8=",
            timestamped_at=datetime(2026, 5, 15, 6, 0, tzinfo=UTC),
            anchored_at=datetime(2026, 5, 15, 6, 5, tzinfo=UTC),
        )


def test_anchor_evidence_rejects_non_hex_root_hash() -> None:
    with pytest.raises(ValueError, match="lowercase hex"):
        AnchorEvidence(
            anchor_id=uuid4(),
            anchor_date=datetime(2026, 5, 15, tzinfo=UTC),
            status="anchored",
            root_hash="A" * 64,  # uppercase
            tsa_identifier="mock-tsa",
            tsr_bytes_b64="AAEC",
            tsa_signature_b64="//8=",
            timestamped_at=datetime(2026, 5, 15, 6, 0, tzinfo=UTC),
            anchored_at=datetime(2026, 5, 15, 6, 5, tzinfo=UTC),
        )


def test_anchor_evidence_rejects_invalid_status() -> None:
    with pytest.raises(ValueError):  # Literal mismatch
        AnchorEvidence(
            anchor_id=uuid4(),
            anchor_date=datetime(2026, 5, 15, tzinfo=UTC),
            status="bogus",  # type: ignore[arg-type]
            root_hash=None,
            tsa_identifier="mock-tsa",
            tsr_bytes_b64=None,
            tsa_signature_b64=None,
            timestamped_at=None,
            anchored_at=datetime(2026, 5, 15, 6, 5, tzinfo=UTC),
        )


# ---------- AnchorEvidence.from_anchor_row helper ----------


def test_from_anchor_row_anchored() -> None:
    row = MagicMock()
    row.id = uuid4()
    row.anchor_date = datetime(2026, 5, 15, tzinfo=UTC)
    row.status = "anchored"
    row.root_hash = "a" * 64
    row.tsa_identifier = "mock-tsa"
    row.tsr_bytes = b"\x00\x01\x02"
    row.tsa_signature = b"\xff" * 32
    row.timestamped_at = datetime(2026, 5, 15, 6, 0, tzinfo=UTC)
    row.anchored_at = datetime(2026, 5, 15, 6, 5, tzinfo=UTC)
    ae = AnchorEvidence.from_anchor_row(row)
    assert ae.status == "anchored"
    assert ae.tsr_bytes_b64 == base64.b64encode(b"\x00\x01\x02").decode("ascii")
    assert ae.tsa_signature_b64 == base64.b64encode(b"\xff" * 32).decode("ascii")
    assert ae.root_hash == "a" * 64


def test_from_anchor_row_deferred_nulls_signature_fields() -> None:
    row = MagicMock()
    row.id = uuid4()
    row.anchor_date = datetime(2026, 5, 15, tzinfo=UTC)
    row.status = "deferred"
    row.root_hash = None
    row.tsa_identifier = "mock-tsa"
    row.tsr_bytes = None
    row.tsa_signature = None
    row.timestamped_at = None
    row.anchored_at = datetime(2026, 5, 15, 6, 5, tzinfo=UTC)
    ae = AnchorEvidence.from_anchor_row(row)
    assert ae.status == "deferred"
    assert ae.tsr_bytes_b64 is None
    assert ae.tsa_signature_b64 is None
    assert ae.timestamped_at is None
    assert ae.root_hash is None


# ---------- build + verify with anchor ----------


@pytest.mark.asyncio
async def test_build_evidence_pack_with_anchored_anchor_binds_root_hash() -> None:
    pairs = await _make_chain(2)
    pack_with_anchor = build_evidence_pack(
        tenant_id=_TENANT,
        generated_at=_GEN,
        scope_start=_NOW,
        scope_end=_LATER,
        receipts_with_snapshots=pairs,
        anchor=_anchored(),
    )
    pack_without_anchor = build_evidence_pack(
        tenant_id=_TENANT,
        generated_at=_GEN,
        scope_start=_NOW,
        scope_end=_LATER,
        receipts_with_snapshots=pairs,
        anchor=None,
    )
    # Anchor-bound pack has a DIFFERENT root_hash than the anchor-less one.
    # If they matched, the anchor wouldn't actually be bound.
    assert pack_with_anchor.root_hash != pack_without_anchor.root_hash
    assert pack_with_anchor.anchor is not None
    assert pack_without_anchor.anchor is None
    assert verify_evidence_pack(pack_with_anchor) is True
    assert verify_evidence_pack(pack_without_anchor) is True


@pytest.mark.asyncio
async def test_build_evidence_pack_with_deferred_anchor_still_binds_root_hash() -> None:
    pairs = await _make_chain(2)
    pack_deferred = build_evidence_pack(
        tenant_id=_TENANT,
        generated_at=_GEN,
        scope_start=_NOW,
        scope_end=_LATER,
        receipts_with_snapshots=pairs,
        anchor=_deferred(),
    )
    pack_anchored = build_evidence_pack(
        tenant_id=_TENANT,
        generated_at=_GEN,
        scope_start=_NOW,
        scope_end=_LATER,
        receipts_with_snapshots=pairs,
        anchor=_anchored(),
    )
    # Deferred and anchored produce DIFFERENT root_hashes - the bind sees
    # different content for the two anchor shapes.
    assert pack_deferred.root_hash != pack_anchored.root_hash
    assert verify_evidence_pack(pack_deferred) is True


@pytest.mark.asyncio
async def test_anchor_tamper_invalidates_pack() -> None:
    pairs = await _make_chain(2)
    pack = build_evidence_pack(
        tenant_id=_TENANT,
        generated_at=_GEN,
        scope_start=_NOW,
        scope_end=_LATER,
        receipts_with_snapshots=pairs,
        anchor=_anchored(),
    )
    assert verify_evidence_pack(pack) is True
    # Tamper the anchor by replacing it with a different one (different
    # anchor_id + tsa_identifier). Same root_hash claim on the pack but
    # different anchor content -> verifier MUST return False.
    tampered_anchor = AnchorEvidence(
        anchor_id=uuid4(),  # different
        anchor_date=pack.anchor.anchor_date,
        status=pack.anchor.status,
        root_hash=pack.anchor.root_hash,
        tsa_identifier="evil-tsa",  # different
        tsr_bytes_b64=pack.anchor.tsr_bytes_b64,
        tsa_signature_b64=pack.anchor.tsa_signature_b64,
        timestamped_at=pack.anchor.timestamped_at,
        anchored_at=pack.anchor.anchored_at,
    )
    tampered_pack = pack.model_copy(update={"anchor": tampered_anchor})
    assert verify_evidence_pack(tampered_pack) is False


@pytest.mark.asyncio
async def test_anchor_added_to_existing_pack_invalidates_root_hash() -> None:
    # Pack was built without anchor; if someone appends an anchor field
    # without recomputing root_hash, the verifier MUST catch it.
    pairs = await _make_chain(2)
    pack_anchorless = build_evidence_pack(
        tenant_id=_TENANT,
        generated_at=_GEN,
        scope_start=_NOW,
        scope_end=_LATER,
        receipts_with_snapshots=pairs,
        anchor=None,
    )
    assert verify_evidence_pack(pack_anchorless) is True
    # Sneak an anchor field into the pack post-bind without recomputing.
    forged = pack_anchorless.model_copy(update={"anchor": _anchored()})
    assert verify_evidence_pack(forged) is False


@pytest.mark.asyncio
async def test_anchor_removed_from_existing_pack_invalidates_root_hash() -> None:
    pairs = await _make_chain(2)
    pack_with = build_evidence_pack(
        tenant_id=_TENANT,
        generated_at=_GEN,
        scope_start=_NOW,
        scope_end=_LATER,
        receipts_with_snapshots=pairs,
        anchor=_anchored(),
    )
    stripped = pack_with.model_copy(update={"anchor": None})
    assert verify_evidence_pack(stripped) is False


@pytest.mark.asyncio
async def test_default_call_omits_anchor_param() -> None:
    # Existing callers (pre-CP9.23) pass no `anchor=` kwarg. This must
    # still produce a valid, verifiable pack to preserve backwards
    # compatibility.
    pairs = await _make_chain(1)
    pack = build_evidence_pack(
        tenant_id=_TENANT,
        generated_at=_GEN,
        scope_start=_NOW,
        scope_end=_LATER,
        receipts_with_snapshots=pairs,
    )
    assert pack.anchor is None
    assert verify_evidence_pack(pack) is True

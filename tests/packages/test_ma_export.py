"""Tests for M&A due diligence export (CP9.28 / BR-13)."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from packages.crypto.sign import generate_keypair
from packages.export.builder import build_evidence_pack
from packages.export.ma_export import (
    MaDiligenceExport,
    MaExportError,
    build_ma_diligence_export,
    daily_chunks,
    verify_ma_diligence_export,
)
from packages.export.schema import AnchorEvidence
from packages.ledger.receipt_builder import build_receipt
from packages.policy.bundle_builder import build_bundle
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.policy.snapshot import capture_snapshot
from packages.schema.receipt import Receipt

_TENANT = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
_OTHER_TENANT = UUID("11111111-2222-3333-4444-555555555555")
_NOW = datetime(2026, 5, 15, 10, 30, tzinfo=UTC)
_SCOPE_START = datetime(2026, 5, 13, tzinfo=UTC)
_SCOPE_END = datetime(2026, 5, 15, tzinfo=UTC)
_CONTENT = {"rules": [{"kind": "x", "decision": "allow"}], "default": "allow"}


async def _make_chain(n: int, tenant: UUID = _TENANT) -> list[tuple[Receipt, UUID]]:
    bundle = build_bundle(tenant_id=tenant, version="1.0.0", content=_CONTENT)
    mock = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )
    verdict = await mock.evaluate(tenant, {"kind": "x"})
    snap = capture_snapshot(bundle, verdict)
    snap_id = uuid4()
    priv, _ = generate_keypair()
    pairs: list[tuple[Receipt, UUID]] = []
    prev: Receipt | None = None
    for i in range(n):
        r = build_receipt(
            tenant_id=tenant,
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


def _anchored_anchor(anchor_date: datetime) -> AnchorEvidence:
    return AnchorEvidence(
        anchor_id=uuid4(),
        anchor_date=anchor_date,
        status="anchored",
        root_hash="a" * 64,
        tsa_identifier="mock-tsa",
        tsr_bytes_b64=base64.b64encode(b"\x00\x01\x02").decode("ascii"),
        tsa_signature_b64=base64.b64encode(b"\xff" * 32).decode("ascii"),
        timestamped_at=anchor_date.replace(hour=23, minute=59),
        anchored_at=anchor_date.replace(hour=23, minute=59, second=59),
    )


# ---------- daily_chunks helper ----------


def test_daily_chunks_one_day() -> None:
    chunks = daily_chunks(datetime(2026, 5, 13, tzinfo=UTC), datetime(2026, 5, 14, tzinfo=UTC))
    assert len(chunks) == 1
    assert chunks[0][0] == datetime(2026, 5, 13, tzinfo=UTC)
    assert chunks[0][1] == datetime(2026, 5, 14, tzinfo=UTC)


def test_daily_chunks_multi_day() -> None:
    chunks = daily_chunks(datetime(2026, 5, 13, tzinfo=UTC), datetime(2026, 5, 16, tzinfo=UTC))
    assert len(chunks) == 3


def test_daily_chunks_partial_last_day() -> None:
    # Scope ends mid-day -> last chunk is shorter than 24h.
    chunks = daily_chunks(
        datetime(2026, 5, 13, tzinfo=UTC),
        datetime(2026, 5, 14, 12, tzinfo=UTC),
    )
    assert len(chunks) == 2
    assert chunks[-1][1] == datetime(2026, 5, 14, 12, tzinfo=UTC)


def test_daily_chunks_rejects_inverted_window() -> None:
    with pytest.raises(MaExportError, match="scope_end"):
        daily_chunks(datetime(2026, 5, 14, tzinfo=UTC), datetime(2026, 5, 13, tzinfo=UTC))


def test_daily_chunks_empty_when_endpoints_equal() -> None:
    same = datetime(2026, 5, 13, tzinfo=UTC)
    chunks = daily_chunks(same, same)
    assert chunks == []


# ---------- build_ma_diligence_export happy path ----------


@pytest.mark.asyncio
async def test_build_ma_export_happy_path_with_two_packs() -> None:
    # Build 2 packs (one per day) + 2 anchored anchors.
    pairs_day1 = await _make_chain(2)
    pairs_day2 = await _make_chain(3)
    pack1 = build_evidence_pack(
        tenant_id=_TENANT,
        generated_at=_NOW,
        scope_start=datetime(2026, 5, 13, tzinfo=UTC),
        scope_end=datetime(2026, 5, 14, tzinfo=UTC),
        receipts_with_snapshots=pairs_day1,
        anchor=_anchored_anchor(datetime(2026, 5, 13, tzinfo=UTC)),
    )
    pack2 = build_evidence_pack(
        tenant_id=_TENANT,
        generated_at=_NOW,
        scope_start=datetime(2026, 5, 14, tzinfo=UTC),
        scope_end=datetime(2026, 5, 15, tzinfo=UTC),
        receipts_with_snapshots=pairs_day2,
        anchor=_anchored_anchor(datetime(2026, 5, 14, tzinfo=UTC)),
    )
    anchors = [
        _anchored_anchor(datetime(2026, 5, 13, tzinfo=UTC)),
        _anchored_anchor(datetime(2026, 5, 14, tzinfo=UTC)),
    ]
    export = build_ma_diligence_export(
        tenant_id=_TENANT,
        scope_start=_SCOPE_START,
        scope_end=_SCOPE_END,
        generated_at=_NOW,
        evidence_packs=[pack1, pack2],
        anchor_proofs=anchors,
    )
    assert isinstance(export, MaDiligenceExport)
    assert export.header.tenant_id == _TENANT
    assert export.header.pack_count == 2
    assert export.header.anchor_count == 2
    assert export.header.total_receipt_count == 5  # 2 + 3
    assert len(export.ma_root_hash) == 64
    assert verify_ma_diligence_export(export) is True


@pytest.mark.asyncio
async def test_build_ma_export_empty_bundle_still_valid() -> None:
    export = build_ma_diligence_export(
        tenant_id=_TENANT,
        scope_start=_SCOPE_START,
        scope_end=_SCOPE_END,
        generated_at=_NOW,
        evidence_packs=[],
        anchor_proofs=[],
    )
    assert export.header.pack_count == 0
    assert export.header.total_receipt_count == 0
    assert verify_ma_diligence_export(export) is True


# ---------- tenant isolation ----------


@pytest.mark.asyncio
async def test_build_ma_export_rejects_cross_tenant_pack() -> None:
    pairs = await _make_chain(1, tenant=_OTHER_TENANT)
    foreign_pack = build_evidence_pack(
        tenant_id=_OTHER_TENANT,
        generated_at=_NOW,
        scope_start=_SCOPE_START,
        scope_end=_SCOPE_END,
        receipts_with_snapshots=pairs,
    )
    with pytest.raises(MaExportError, match="belongs to tenant"):
        build_ma_diligence_export(
            tenant_id=_TENANT,
            scope_start=_SCOPE_START,
            scope_end=_SCOPE_END,
            generated_at=_NOW,
            evidence_packs=[foreign_pack],
            anchor_proofs=[],
        )


# ---------- size limits ----------


def test_build_ma_export_rejects_inverted_scope_window() -> None:
    with pytest.raises(MaExportError, match="scope_end"):
        build_ma_diligence_export(
            tenant_id=_TENANT,
            scope_start=_SCOPE_END,
            scope_end=_SCOPE_START,
            generated_at=_NOW,
            evidence_packs=[],
            anchor_proofs=[],
        )


# ---------- tamper detection ----------


@pytest.mark.asyncio
async def test_ma_export_tamper_with_pack_invalidates_bundle() -> None:
    pairs = await _make_chain(2)
    pack = build_evidence_pack(
        tenant_id=_TENANT,
        generated_at=_NOW,
        scope_start=_SCOPE_START,
        scope_end=_SCOPE_END,
        receipts_with_snapshots=pairs,
    )
    export = build_ma_diligence_export(
        tenant_id=_TENANT,
        scope_start=_SCOPE_START,
        scope_end=_SCOPE_END,
        generated_at=_NOW,
        evidence_packs=[pack],
        anchor_proofs=[],
    )
    assert verify_ma_diligence_export(export) is True
    # Swap the pack with a different one (same tenant, different receipts).
    pairs2 = await _make_chain(3)
    different_pack = build_evidence_pack(
        tenant_id=_TENANT,
        generated_at=_NOW,
        scope_start=_SCOPE_START,
        scope_end=_SCOPE_END,
        receipts_with_snapshots=pairs2,
    )
    forged = export.model_copy(update={"evidence_packs": [different_pack]})
    assert verify_ma_diligence_export(forged) is False


@pytest.mark.asyncio
async def test_ma_export_tamper_with_anchor_invalidates_bundle() -> None:
    pairs = await _make_chain(1)
    pack = build_evidence_pack(
        tenant_id=_TENANT,
        generated_at=_NOW,
        scope_start=_SCOPE_START,
        scope_end=_SCOPE_END,
        receipts_with_snapshots=pairs,
    )
    anchor = _anchored_anchor(datetime(2026, 5, 13, tzinfo=UTC))
    export = build_ma_diligence_export(
        tenant_id=_TENANT,
        scope_start=_SCOPE_START,
        scope_end=_SCOPE_END,
        generated_at=_NOW,
        evidence_packs=[pack],
        anchor_proofs=[anchor],
    )
    different_anchor = _anchored_anchor(datetime(2026, 5, 14, tzinfo=UTC))
    forged = export.model_copy(update={"anchor_proofs": [different_anchor]})
    assert verify_ma_diligence_export(forged) is False


# ---------- header tz-awareness ----------


@pytest.mark.asyncio
async def test_ma_export_rejects_naive_scope_start() -> None:
    with pytest.raises(MaExportError, match="timezone-aware"):
        build_ma_diligence_export(
            tenant_id=_TENANT,
            scope_start=datetime(2026, 5, 13),  # naive
            scope_end=_SCOPE_END,
            generated_at=_NOW,
            evidence_packs=[],
            anchor_proofs=[],
        )

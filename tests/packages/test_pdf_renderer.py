"""Tests for evidence pack PDF renderer (CP9.21, closes BR-05 second half)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from packages.crypto.sign import generate_keypair
from packages.export.builder import build_evidence_pack
from packages.export.pdf_renderer import (
    PdfRenderError,
    _anchor_table,
    _pin_pdf_timestamps,
    _short_hex,
    _truncate,
    render_evidence_pack_pdf,
)
from packages.export.schema import AnchorEvidence, EvidencePack
from packages.ledger.receipt_builder import build_receipt
from packages.policy.bundle_builder import build_bundle
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.policy.snapshot import capture_snapshot
from packages.schema.receipt import Receipt

_TENANT_A = UUID("55555555-6666-7777-8888-999999999999")
_NOW = datetime(2026, 5, 15, 5, 0, tzinfo=UTC)
_LATER = datetime(2026, 5, 15, 7, 0, tzinfo=UTC)
_GEN = datetime(2026, 5, 15, 6, 30, tzinfo=UTC)
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


async def _make_pack(n: int) -> EvidencePack:
    pairs = await _make_chain(n)
    return build_evidence_pack(
        tenant_id=_TENANT_A,
        generated_at=_GEN,
        scope_start=_NOW,
        scope_end=_LATER,
        receipts_with_snapshots=pairs,
    )


# ---------- happy-path renders ----------


@pytest.mark.asyncio
async def test_renders_pack_with_three_receipts_to_pdf_bytes() -> None:
    pack = await _make_pack(3)
    pdf = render_evidence_pack_pdf(pack)
    assert isinstance(pdf, bytes)
    assert len(pdf) > 1000
    assert pdf.startswith(b"%PDF-")
    assert pdf.rstrip().endswith(b"%%EOF")


@pytest.mark.asyncio
async def test_renders_empty_pack_without_raising() -> None:
    pack = build_evidence_pack(
        tenant_id=_TENANT_A,
        generated_at=_GEN,
        scope_start=_NOW,
        scope_end=_LATER,
        receipts_with_snapshots=[],
    )
    pdf = render_evidence_pack_pdf(pack)
    assert pdf.startswith(b"%PDF-")
    assert b"no receipts in scope" in pdf or b"(no receipts" in pdf


@pytest.mark.asyncio
async def test_renders_single_receipt_pack() -> None:
    pack = await _make_pack(1)
    pdf = render_evidence_pack_pdf(pack)
    assert pdf.startswith(b"%PDF-")
    # Genesis marker: ( and ) are PDF special chars and get escaped to \( \)
    # inside content streams. Accept either form.
    assert b"(genesis)" in pdf or b"\\(genesis\\)" in pdf


# ---------- pagination ----------


@pytest.mark.asyncio
async def test_renders_large_pack_paginates_over_multiple_pages() -> None:
    pack = await _make_pack(60)
    pdf = render_evidence_pack_pdf(pack)
    # Count /Type /Page entries (PDF page objects). A 60-receipt pack must
    # exceed one page given our row height + A4 margins.
    page_object_count = pdf.count(b"/Type /Page\n") + pdf.count(b"/Type /Page ")
    # Fallback heuristic: ReportLab also writes /Type/Page with no space.
    if page_object_count == 0:
        page_object_count = pdf.count(b"/Type/Page")
    assert (
        page_object_count >= 2
    ), f"expected multi-page output for 60 receipts, found {page_object_count} page objects"


# ---------- header content present ----------


@pytest.mark.asyncio
async def test_header_table_contains_tenant_id_and_full_root_hash() -> None:
    pack = await _make_pack(2)
    pdf = render_evidence_pack_pdf(pack)
    # Tenant UUID is rendered in the header table. PDF text is encoded but
    # ASCII strings inside parens come through as-is for our font choices.
    assert str(pack.header.tenant_id).encode("ascii") in pdf
    assert pack.root_hash.encode("ascii") in pdf
    assert str(pack.header.pack_id).encode("ascii") in pdf


@pytest.mark.asyncio
async def test_receipt_count_zero_is_rendered() -> None:
    pack = build_evidence_pack(
        tenant_id=_TENANT_A,
        generated_at=_GEN,
        scope_start=_NOW,
        scope_end=_LATER,
        receipts_with_snapshots=[],
    )
    pdf = render_evidence_pack_pdf(pack)
    assert b"Receipt count" in pdf


# ---------- determinism ----------


@pytest.mark.asyncio
async def test_two_renders_of_same_pack_are_byte_identical() -> None:
    pack = await _make_pack(4)
    a = render_evidence_pack_pdf(pack)
    b = render_evidence_pack_pdf(pack)
    assert a == b, "renders must be byte-identical (pinned timestamps)"


@pytest.mark.asyncio
async def test_two_renders_of_empty_pack_are_byte_identical() -> None:
    pack = build_evidence_pack(
        tenant_id=_TENANT_A,
        generated_at=_GEN,
        scope_start=_NOW,
        scope_end=_LATER,
        receipts_with_snapshots=[],
    )
    a = render_evidence_pack_pdf(pack)
    b = render_evidence_pack_pdf(pack)
    assert a == b


# ---------- input validation ----------


def test_render_rejects_non_pack_input() -> None:
    with pytest.raises(PdfRenderError):
        render_evidence_pack_pdf("not a pack")  # type: ignore[arg-type]


def test_render_rejects_dict_input() -> None:
    with pytest.raises(PdfRenderError):
        render_evidence_pack_pdf({"header": {}, "receipts": []})  # type: ignore[arg-type]


def test_render_rejects_none() -> None:
    with pytest.raises(PdfRenderError):
        render_evidence_pack_pdf(None)  # type: ignore[arg-type]


# ---------- helpers: _truncate ----------


def test_truncate_short_string_passes_through() -> None:
    assert _truncate("hello") == "hello"


def test_truncate_long_string_appends_ellipsis() -> None:
    s = "x" * 200
    out = _truncate(s, limit=50)
    assert len(out) == 50
    assert out.endswith("\u2026")


def test_truncate_at_exact_limit_passes_through() -> None:
    s = "x" * 50
    assert _truncate(s, limit=50) == s


# ---------- helpers: _short_hex ----------


def test_short_hex_full_length_truncates() -> None:
    full = "a" * 64
    out = _short_hex(full)
    assert "\u2026" in out
    assert out.startswith("a" * 12)
    assert out.endswith("a" * 4)


def test_short_hex_under_threshold_passes_through() -> None:
    assert _short_hex("abc") == "abc"


def test_short_hex_at_boundary_passes_through() -> None:
    # 12 head + 4 tail + 1 ellipsis = 17 chars; anything <= 17 should pass.
    assert _short_hex("a" * 17) == "a" * 17


# ---------- helpers: _pin_pdf_timestamps ----------


def test_pin_pdf_timestamps_overwrites_creation_and_mod() -> None:
    raw = b"head /CreationDate (D:19700101000000+00'00') middle /ModDate (D:19700101000000+00'00') tail"
    ts = datetime(2026, 5, 15, 6, 30, 0, tzinfo=UTC)
    out = _pin_pdf_timestamps(raw, ts)
    assert b"D:20260515063000+00'00'" in out
    assert b"D:19700101000000" not in out


def test_pin_pdf_timestamps_handles_naive_timestamp() -> None:
    # If somehow a naive datetime arrives (schema makes this impossible at the
    # pack level, but the helper is defensive): utcoffset() returns None and
    # the branch takes 0-minute offset.
    raw = b"/CreationDate (D:19700101000000+00'00') /ModDate (D:19700101000000+00'00')"
    naive = datetime(2026, 5, 15, 6, 30, 0)
    out = _pin_pdf_timestamps(raw, naive)
    assert b"D:20260515063000+00'00'" in out


def test_pin_pdf_timestamps_negative_offset() -> None:
    from datetime import timedelta, timezone

    raw = b"/CreationDate (D:19700101000000+00'00') /ModDate (D:19700101000000+00'00')"
    tz = timezone(timedelta(hours=-5))
    ts = datetime(2026, 5, 15, 6, 30, 0, tzinfo=tz)
    out = _pin_pdf_timestamps(raw, ts)
    assert b"-05'00'" in out


def test_pin_pdf_timestamps_passes_through_when_no_match() -> None:
    raw = b"no date fields here at all"
    ts = datetime(2026, 5, 15, 6, 30, 0, tzinfo=UTC)
    out = _pin_pdf_timestamps(raw, ts)
    assert out == raw


# ---------- unicode / encoding ----------


@pytest.mark.asyncio
async def test_pack_renders_with_unicode_in_payload() -> None:
    # Even though the renderer pulls structural fields (UUIDs, hashes,
    # timestamps) and not payload text, this test confirms a pack built from
    # events whose payload carries unicode (via the underlying bundle
    # content) does not blow up the renderer.
    bundle = build_bundle(
        tenant_id=_TENANT_A,
        version="1.0.0",
        content={"rules": [{"kind": "x", "decision": "allow"}], "default": "allow"},
    )
    mock = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )
    verdict = await mock.evaluate(_TENANT_A, {"kind": "x"})
    snap = capture_snapshot(bundle, verdict)
    snap_id = uuid4()
    priv, _ = generate_keypair()
    r = build_receipt(
        tenant_id=_TENANT_A,
        event_id=uuid4(),
        event_payload={"note": "café — déjà vu — 日本語"},
        policy_snapshot=snap,
        policy_snapshot_id=snap_id,
        prev_receipt=None,
        tenant_signing_key=priv,
    )
    pack = build_evidence_pack(
        tenant_id=_TENANT_A,
        generated_at=_GEN,
        scope_start=_NOW,
        scope_end=_LATER,
        receipts_with_snapshots=[(r, snap_id)],
    )
    pdf = render_evidence_pack_pdf(pack)
    assert pdf.startswith(b"%PDF-")


# ---------- activities block ----------


@pytest.mark.asyncio
async def test_activities_block_contains_iris() -> None:
    pack = await _make_pack(2)
    pdf = render_evidence_pack_pdf(pack)
    # Every receipt has a PROV-O activity; the IRI prefix appears.
    assert b"urn:forensa:activity:" in pdf
    assert b"urn:forensa:event:" in pdf
    assert b"urn:forensa:receipt:" in pdf


# ---------- footer ----------


@pytest.mark.asyncio
async def test_footer_present_on_pages() -> None:
    pack = await _make_pack(3)
    pdf = render_evidence_pack_pdf(pack)
    assert b"verify against root_hash" in pdf
    assert b"Page" in pdf


# ---------- anchor block (CP9.23 + NEW-P9.23.pdf-anchor-display) ----------


def _anchored_anchor() -> AnchorEvidence:
    import base64

    return AnchorEvidence(
        anchor_id=uuid4(),
        anchor_date=datetime(2026, 5, 13, tzinfo=UTC),
        status="anchored",
        root_hash="a" * 64,
        tsa_identifier="mock-tsa",
        tsr_bytes_b64=base64.b64encode(
            b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f"
        ).decode("ascii"),
        tsa_signature_b64=base64.b64encode(b"\xff" * 32).decode("ascii"),
        timestamped_at=datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
        anchored_at=datetime(2026, 5, 13, 12, 5, tzinfo=UTC),
    )


def _deferred_anchor() -> AnchorEvidence:
    return AnchorEvidence(
        anchor_id=uuid4(),
        anchor_date=datetime(2026, 5, 13, tzinfo=UTC),
        status="deferred",
        root_hash=None,
        tsa_identifier="mock-tsa",
        tsr_bytes_b64=None,
        tsa_signature_b64=None,
        timestamped_at=None,
        anchored_at=datetime(2026, 5, 13, 12, 5, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_pdf_contains_anchor_section_when_anchor_present() -> None:
    pairs = await _make_chain(2)
    pack = build_evidence_pack(
        tenant_id=_TENANT_A,
        generated_at=_GEN,
        scope_start=_NOW,
        scope_end=_LATER,
        receipts_with_snapshots=pairs,
        anchor=_anchored_anchor(),
    )
    pdf = render_evidence_pack_pdf(pack)
    assert pdf.startswith(b"%PDF-")
    # Anchor section header MUST appear.
    assert b"RFC 3161 TSA anchor proof" in pdf
    assert b"openssl ts -verify" in pdf
    # Anchored row fields surface.
    assert b"anchored" in pdf
    assert b"mock-tsa" in pdf


@pytest.mark.asyncio
async def test_pdf_omits_anchor_section_when_no_anchor() -> None:
    pairs = await _make_chain(2)
    pack = build_evidence_pack(
        tenant_id=_TENANT_A,
        generated_at=_GEN,
        scope_start=_NOW,
        scope_end=_LATER,
        receipts_with_snapshots=pairs,
        anchor=None,
    )
    pdf = render_evidence_pack_pdf(pack)
    # No anchor in pack -> section header MUST be absent.
    assert b"RFC 3161 TSA anchor proof" not in pdf


@pytest.mark.asyncio
async def test_pdf_anchor_section_shows_not_anchored_for_deferred_tombstone() -> None:
    pairs = await _make_chain(1)
    pack = build_evidence_pack(
        tenant_id=_TENANT_A,
        generated_at=_GEN,
        scope_start=_NOW,
        scope_end=_LATER,
        receipts_with_snapshots=pairs,
        anchor=_deferred_anchor(),
    )
    pdf = render_evidence_pack_pdf(pack)
    # Section appears (regulator must know the day was scheduled) but
    # signature fields read "not anchored".
    assert b"RFC 3161 TSA anchor proof" in pdf
    assert b"deferred" in pdf
    assert b"not anchored" in pdf


def test_anchor_table_returns_none_for_none_anchor() -> None:
    # Test the helper directly. _anchor_table(pack) returns None when
    # pack.anchor is None - the caller uses this to omit the section.
    pack = MagicMock(spec=EvidencePack)
    pack.anchor = None
    assert _anchor_table(pack) is None

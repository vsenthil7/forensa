"""Evidence pack PDF renderer (CP9.21).

Closes BR-05 second half: regulator-grade evidence pack now ships in two wire
forms, JSON-LD (machine-readable, verifiable) and PDF (human-readable, court
exhibit-style). The PDF is a deterministic rendering of the same pack content
the JSON-LD form binds in root_hash, so a regulator can hand the PDF to a
forensic accountant and the JSON-LD to a developer in parallel and they will
agree on every fact.

Determinism note: ReportLab embeds a creation timestamp by default which would
break byte-identical reproduction of the same pack. We pin the document's
"info dict" to pack.header.generated_at so two renders of the same pack
produce byte-identical bytes. This is important because (in a future CP)
the PDF rendering will itself be bound into a Receipt; today it is at least
hashable and stable.

PRODUCTION-DEFERRED: a detached platform signature on the PDF is tracked as
NEW-P11.6 (review item #12) alongside the same gap on the JSON-LD form.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Final

from reportlab.lib import colors  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore[import-untyped]
from reportlab.lib.units import mm  # type: ignore[import-untyped]
from reportlab.pdfgen.canvas import Canvas  # type: ignore[import-untyped]
from reportlab.platypus import (  # type: ignore[import-untyped]
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from packages.export.schema import EvidencePack

# Visual constants. Pinned so two renders of the same pack are byte-identical.
_PAGE_SIZE = A4
_LEFT_MARGIN: Final[float] = 18 * mm
_RIGHT_MARGIN: Final[float] = 18 * mm
_TOP_MARGIN: Final[float] = 18 * mm
_BOTTOM_MARGIN: Final[float] = 18 * mm

# Compression OFF for content streams. Two reasons: (a) deterministic output
# (zlib output is technically deterministic but implementations vary across
# Python builds, and an uncompressed stream sidesteps the question entirely);
# (b) lets verifiers grep the raw PDF bytes for tenant UUIDs / hashes / IRIs
# without first running an unzip pass. Trade-off: PDF size is ~2-4x larger.
# Acceptable for an evidence artifact that lives on long-term storage and is
# read by humans + forensic tools, not served at scale.
_PDF_COMPRESS = 0

# Hard ceiling on reasoning/payload text inside the table cells. Anything
# longer truncates with an ellipsis so the PDF remains readable and the
# table layout does not overflow. Full content stays available in the
# JSON-LD form bound by root_hash.
_TEXT_CELL_MAX: Final[int] = 80


class PdfRenderError(ValueError):
    """Raised when an EvidencePack cannot be rendered to PDF."""


def _truncate(s: str, limit: int = _TEXT_CELL_MAX) -> str:
    if len(s) <= limit:
        return s
    return s[: limit - 1] + "\u2026"


def _short_hex(h: str, head: int = 12, tail: int = 4) -> str:
    """Render a 64-char hex digest as head\u2026tail for table cells.

    The full hex is reproduced in the header table; this short form is for
    the per-receipt rows where horizontal space is constrained.
    """
    if len(h) <= head + tail + 1:
        return h
    return f"{h[:head]}\u2026{h[-tail:]}"


def _header_table(pack: EvidencePack) -> Table:
    h = pack.header
    rows = [
        ["Tenant", str(h.tenant_id)],
        ["Pack ID", str(h.pack_id)],
        ["Scope start", h.scope_start.isoformat()],
        ["Scope end", h.scope_end.isoformat()],
        ["Generated at", h.generated_at.isoformat()],
        ["Receipt count", str(h.receipt_count)],
        ["Root hash (SHA-256)", pack.root_hash],
    ]
    table = Table(rows, colWidths=[42 * mm, 130 * mm])
    table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
                ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 0.2, colors.grey),
                ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return table


def _receipts_table(pack: EvidencePack) -> Table:
    header_row = ["Seq", "Receipt ID", "Signed at (UTC)", "Receipt hash", "Prev hash"]
    rows: list[list[str]] = [header_row]
    for r in pack.receipts:
        rows.append(
            [
                str(r.sequence),
                _truncate(str(r.id), 36),
                r.signed_at.isoformat(),
                _short_hex(r.receipt_hash),
                _short_hex(r.prev_receipt_hash) if r.prev_receipt_hash else "(genesis)",
            ]
        )
    table = Table(
        rows,
        colWidths=[12 * mm, 64 * mm, 42 * mm, 30 * mm, 24 * mm],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "Helvetica", 8),
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 0.2, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return table


def _activities_table(pack: EvidencePack) -> Table:
    header_row = ["Activity IRI", "Used event", "Used snapshot", "Generated receipt"]
    rows: list[list[str]] = [header_row]
    for a in pack.activities:
        rows.append(
            [
                _truncate(a.id, 50),
                _truncate(a.used_event, 50),
                _truncate(a.used_policy_snapshot, 50),
                _truncate(a.generated_receipt, 50),
            ]
        )
    table = Table(
        rows,
        colWidths=[42 * mm, 42 * mm, 42 * mm, 46 * mm],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "Helvetica", 7),
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 0.2, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return table


def _footer_callback(canvas: Canvas, doc: SimpleDocTemplate) -> None:
    """Draw a page number + verification reminder at the bottom of every page."""
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.grey)
    canvas.drawString(
        _LEFT_MARGIN,
        10 * mm,
        "Forensa Evidence Pack \u2014 verify against root_hash on JSON-LD form.",
    )
    canvas.drawRightString(
        _PAGE_SIZE[0] - _RIGHT_MARGIN,
        10 * mm,
        f"Page {canvas.getPageNumber()}",
    )
    canvas.restoreState()


def render_evidence_pack_pdf(pack: EvidencePack) -> bytes:
    """Render an EvidencePack to PDF bytes.

    The output is deterministic for a given pack: the document's metadata
    (creation date, mod date, producer) is pinned to pack.header.generated_at
    and a fixed producer string so two renders are byte-identical.

    Pages may flow naturally for packs with many receipts; the receipts and
    activities tables both set ``repeatRows=1`` so the header row repeats
    on every continuation page.
    """
    if not isinstance(pack, EvidencePack):
        raise PdfRenderError("pack must be an EvidencePack")

    buf = io.BytesIO()

    # Pin metadata for byte-deterministic output. Without this, ReportLab
    # stamps the current wall-clock time into the PDF info dict and two
    # renders of the same pack would differ.
    pinned_ts = pack.header.generated_at
    doc = SimpleDocTemplate(
        buf,
        pagesize=_PAGE_SIZE,
        leftMargin=_LEFT_MARGIN,
        rightMargin=_RIGHT_MARGIN,
        topMargin=_TOP_MARGIN,
        bottomMargin=_BOTTOM_MARGIN,
        title=f"Forensa Evidence Pack {pack.header.pack_id}",
        author="Forensa",
        subject=f"Tenant {pack.header.tenant_id}",
        creator="Forensa Evidence Pack PDF Renderer (CP9.21)",
        producer="Forensa Evidence Pack PDF Renderer (CP9.21)",
        invariant=1,
        pageCompression=_PDF_COMPRESS,
    )
    # ReportLab uses _calc.set_invariant pattern but the
    # cleanest way to pin the timestamps is to overwrite after build.
    # We do that via canvas's _doc.info hook below.

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ForensaTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        spaceAfter=6,
    )
    h2_style = ParagraphStyle(
        "ForensaH2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        spaceAfter=4,
        spaceBefore=8,
    )
    body_style = ParagraphStyle(
        "ForensaBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=11,
    )

    story: list[object] = []
    story.append(Paragraph("Forensa Evidence Pack", title_style))
    story.append(
        Paragraph(
            "Regulator-grade evidence bundle. The JSON-LD form is the cryptographic "
            "source of truth; this PDF is a human-readable rendering of the same "
            "content bound by the root_hash printed below. Any divergence between "
            "this PDF and the JSON-LD form is a tamper indicator on either copy.",
            body_style,
        )
    )
    story.append(Spacer(1, 6))

    story.append(Paragraph("Pack header", h2_style))
    story.append(_header_table(pack))

    story.append(Paragraph("Receipts", h2_style))
    if pack.receipts:
        story.append(_receipts_table(pack))
    else:
        story.append(
            Paragraph("(no receipts in scope)", body_style),
        )

    story.append(Paragraph("PROV-O activities", h2_style))
    if pack.activities:
        story.append(_activities_table(pack))
    else:
        story.append(
            Paragraph("(no activities)", body_style),
        )

    def _on_first_page(canvas: Canvas, doc: SimpleDocTemplate) -> None:
        _footer_callback(canvas, doc)

    def _on_later_pages(canvas: Canvas, doc: SimpleDocTemplate) -> None:
        _footer_callback(canvas, doc)

    doc.build(story, onFirstPage=_on_first_page, onLaterPages=_on_later_pages)

    raw = buf.getvalue()
    # Post-process: pin /CreationDate and /ModDate in the PDF info dict so
    # two renders produce byte-identical output. ReportLab writes these as
    # PDF date strings like D:YYYYMMDDHHmmSS+ZZ'zz'. We replace whatever
    # ReportLab put in with a value derived solely from pack.header.generated_at.
    return _pin_pdf_timestamps(raw, pinned_ts)


def _pin_pdf_timestamps(raw: bytes, ts: datetime) -> bytes:
    """Rewrite /CreationDate and /ModDate to a value derived from ts.

    ReportLab honours TZ offset; we render UTC always since pack.header.generated_at
    is required tz-aware (the schema validator enforces it).
    """
    import re

    # PDF date syntax: (D:YYYYMMDDHHmmSS+HH'mm')
    offset = ts.utcoffset()
    offset_minutes = int(offset.total_seconds() // 60) if offset is not None else 0
    sign = "+" if offset_minutes >= 0 else "-"
    hh = abs(offset_minutes) // 60
    mm_ = abs(offset_minutes) % 60
    pdf_date = f"(D:{ts.strftime('%Y%m%d%H%M%S')}{sign}{hh:02d}'{mm_:02d}')"

    pat_creation = re.compile(rb"/CreationDate \([^)]*\)")
    pat_mod = re.compile(rb"/ModDate \([^)]*\)")
    out = pat_creation.sub(b"/CreationDate " + pdf_date.encode("ascii"), raw)
    out = pat_mod.sub(b"/ModDate " + pdf_date.encode("ascii"), out)
    return out

"""M&A due diligence export (CP9.28 / BR-13).

An M&A acquirer or their forensic accountant needs the full evidence trail
for a target's AI agent workload over a date range, packaged as a single
sealed deliverable suitable for inclusion in a virtual data room. The
deliverable is:

    MaDiligenceExport
      ├── header (tenant_id, scope_start, scope_end, generated_at,
      │           pack_count, total_receipt_count, anchor_count)
      ├── evidence_packs: list[EvidencePack]  (one per chunk)
      ├── anchor_proofs:  list[AnchorEvidence]
      └── ma_root_hash    SHA-256 over canonical_json of the above

The acquirer verifies the bundle's integrity by recomputing ma_root_hash
from the canonical bind shape. If it matches the published value, every
embedded EvidencePack's root_hash is also verifiable independently, and
every embedded anchor's TSR can be re-verified via openssl ts -verify
against the chain root recorded in the anchor.

Why chunking the scope window: a single EvidencePack is capped at 1000
receipts (_MAX_RECEIPTS_PER_PACK in routes/evidence.py). M&A scope
windows can span 12-24 months and tens of thousands of Receipts. The
exporter chunks the scope window by anchored day so each EvidencePack
fits under the cap AND each pack's root_hash is bound to exactly one
day's TSA anchor.

PRODUCTION-DEFERRED:
- NEW-P10.X.ma-export-encryption-at-rest: encrypt the bundle with the
  acquirer's public key so only they can decrypt it.
- NEW-P11.X.ma-export-detached-platform-signature: sign the bundle with
  Forensa's platform key so the acquirer can verify provenance.
- NEW-P12.X.ma-export-streaming: today the full bundle is built in memory
  (~1-10 MB per 1000 receipts); for 100K+ receipt exports stream the
  bundle to S3 with multipart upload.
- NEW-P12.X.ma-export-async-job: today this is synchronous; for very
  large windows return a job_id and let the caller poll.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from packages.crypto.hash import sha256_hex
from packages.export.schema import AnchorEvidence, EvidencePack

_MAX_PACKS_PER_EXPORT = 366  # one year-worth of daily anchored packs
_MAX_TOTAL_RECEIPTS = 100_000  # hard ceiling on bundle size


class MaExportError(ValueError):
    """Raised when an M&A export cannot be assembled."""


class MaDiligenceHeader(BaseModel):
    """Manifest header for an M&A due diligence export."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    export_id: UUID = Field(..., description="UUID of this export bundle")
    tenant_id: UUID = Field(..., description="Target tenant whose evidence this is")
    generated_at: datetime = Field(..., description="UTC timestamp when the bundle was assembled")
    scope_start: datetime = Field(..., description="Inclusive start of M&A scope window")
    scope_end: datetime = Field(..., description="Inclusive end of M&A scope window")
    pack_count: int = Field(..., ge=0, description="Number of EvidencePacks in the bundle")
    anchor_count: int = Field(..., ge=0, description="Number of distinct TSA anchors in the bundle")
    total_receipt_count: int = Field(..., ge=0, description="Sum of receipt_count across packs")

    @field_validator("generated_at", "scope_start", "scope_end")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware (UTC)")
        return v


class MaDiligenceExport(BaseModel):
    """Sealed M&A due diligence bundle.

    `ma_root_hash` binds the canonical JSON of (header, evidence_packs,
    anchor_proofs) so the acquirer can verify the bundle's integrity
    independently of Forensa's API.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    export_type: str = Field(default="forensa:MaDiligenceExport", alias="@type")
    header: MaDiligenceHeader
    evidence_packs: list[EvidencePack]
    anchor_proofs: list[AnchorEvidence]
    ma_root_hash: str = Field(..., min_length=64, max_length=64)

    @field_validator("ma_root_hash")
    @classmethod
    def _root_hex(cls, v: str) -> str:
        if not all(c in "0123456789abcdef" for c in v):
            raise ValueError("ma_root_hash must be lowercase hex")
        return v


def build_ma_diligence_export(
    *,
    tenant_id: UUID,
    scope_start: datetime,
    scope_end: datetime,
    generated_at: datetime,
    evidence_packs: list[EvidencePack],
    anchor_proofs: list[AnchorEvidence],
) -> MaDiligenceExport:
    """Compose an M&A due diligence export from pre-built EvidencePacks + anchors.

    Caller is responsible for:
      - Chunking the scope window into per-day or per-N-receipt slices
        and building one EvidencePack per slice.
      - Collecting the distinct anchor rows that cover the scope window.

    The exporter validates:
      - All EvidencePacks belong to ``tenant_id``.
      - Pack count <= ``_MAX_PACKS_PER_EXPORT`` (366).
      - Total receipt count across packs <= ``_MAX_TOTAL_RECEIPTS`` (100K).
      - scope_end >= scope_start, both tz-aware.

    The output's ``ma_root_hash`` binds the header + every pack's
    root_hash + every anchor's anchor_id so any tamper of any included
    artefact invalidates the bundle.
    """
    if scope_start.tzinfo is None or scope_end.tzinfo is None:
        raise MaExportError("scope_start and scope_end must be timezone-aware (UTC)")
    if scope_end < scope_start:
        raise MaExportError("scope_end must be >= scope_start")
    if len(evidence_packs) > _MAX_PACKS_PER_EXPORT:
        raise MaExportError(f"too many packs: {len(evidence_packs)} > {_MAX_PACKS_PER_EXPORT}")
    total_receipts = sum(p.header.receipt_count for p in evidence_packs)
    if total_receipts > _MAX_TOTAL_RECEIPTS:
        raise MaExportError(
            f"bundle exceeds {_MAX_TOTAL_RECEIPTS} receipts ({total_receipts}); "
            "narrow the scope or split the export"
        )
    for p in evidence_packs:
        if p.header.tenant_id != tenant_id:
            raise MaExportError(
                f"pack {p.header.pack_id} belongs to tenant {p.header.tenant_id}, "
                f"not {tenant_id}"
            )

    header = MaDiligenceHeader(
        export_id=uuid4(),
        tenant_id=tenant_id,
        generated_at=generated_at,
        scope_start=scope_start,
        scope_end=scope_end,
        pack_count=len(evidence_packs),
        anchor_count=len(anchor_proofs),
        total_receipt_count=total_receipts,
    )

    # Bind ma_root_hash over:
    #   - header (binds scope window, counts, tenant id)
    #   - every pack's root_hash (binds each pack's full content via its
    #     own internal root_hash; we don't re-bind the full pack content
    #     because that would be redundant — pack.root_hash already covers it)
    #   - every anchor's anchor_id + root_hash (binds the TSA proofs)
    bind: dict[str, object] = {
        "header": header.model_dump(mode="json"),
        "pack_root_hashes": [p.root_hash for p in evidence_packs],
        "anchor_ids": sorted(str(a.anchor_id) for a in anchor_proofs),
        "anchor_root_hashes": [a.root_hash or "" for a in anchor_proofs],
    }
    ma_root_hash = sha256_hex(bind)

    return MaDiligenceExport(
        header=header,
        evidence_packs=evidence_packs,
        anchor_proofs=anchor_proofs,
        ma_root_hash=ma_root_hash,
    )


def verify_ma_diligence_export(export: MaDiligenceExport) -> bool:
    """Recompute ma_root_hash from the export content; True iff matches.

    Independent verifier the M&A acquirer can run on the bundle without
    contacting Forensa. Symmetric with build_ma_diligence_export's bind
    shape.
    """
    bind: dict[str, object] = {
        "header": export.header.model_dump(mode="json"),
        "pack_root_hashes": [p.root_hash for p in export.evidence_packs],
        "anchor_ids": sorted(str(a.anchor_id) for a in export.anchor_proofs),
        "anchor_root_hashes": [a.root_hash or "" for a in export.anchor_proofs],
    }
    return sha256_hex(bind) == export.ma_root_hash


def daily_chunks(scope_start: datetime, scope_end: datetime) -> list[tuple[datetime, datetime]]:
    """Yield (chunk_start, chunk_end) pairs covering the scope window day-by-day.

    Each pair represents one UTC day. The acquirer chunks the export per
    anchored day so each pack maps 1:1 with one TSA anchor. Helper used
    by the route layer; pure function for easy testing.
    """
    if scope_end < scope_start:
        raise MaExportError("scope_end must be >= scope_start")
    chunks: list[tuple[datetime, datetime]] = []
    cursor = scope_start
    while cursor < scope_end:
        next_day = cursor + timedelta(days=1)
        chunk_end = min(next_day, scope_end)
        chunks.append((cursor, chunk_end))
        cursor = next_day
    return chunks

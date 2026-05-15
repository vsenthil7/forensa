"""Evidence pack JSON-LD/PROV-O Pydantic schema (CP6.1).

An EvidencePack is the canonical tamper-evident bundle a compliance officer
exports to hand to a regulator or auditor. It binds:

- A header (tenant id, scope window, generation timestamp)
- A list of Receipts in scope (sorted by sequence ASC; chain replayable)
- A PROV-O activity graph describing how each Receipt was produced
- A merkle-style root_hash binding the whole pack content

The wire form uses JSON-LD with @context anchoring at https://forensa.dev/ld/v1.
The PROV-O block follows the W3C PROV-O recommendation:
  https://www.w3.org/TR/prov-o/
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

JSONLD_CONTEXT = "https://forensa.dev/ld/v1"
PROV_NS = "http://www.w3.org/ns/prov#"
FORENSA_NS = "https://forensa.dev/ns#"


class AnchorEvidence(BaseModel):
    """RFC 3161 TSA anchor proof embedded inside an EvidencePack (CP9.23).

    Carries enough data for an offline verifier to re-verify the TSA
    signature over the chain root without an additional API call. When
    the originating ``TimestampAnchorRow`` had ``status='anchored'``,
    all four of (root_hash, tsr_bytes_b64, tsa_signature_b64,
    timestamped_at) are populated; when ``status='deferred'`` they are
    None and ``anchor_id`` + ``status`` + ``tsa_identifier`` +
    ``anchored_at`` are populated alone (the pack still records that the
    day was scheduled for anchoring, even if the TSA call did not
    succeed).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    anchor_id: UUID = Field(..., description="UUID of the source TimestampAnchorRow")
    anchor_date: datetime = Field(..., description="UTC midnight of the anchored day")
    status: Literal["anchored", "deferred"]
    root_hash: str | None = Field(
        ..., description="Chain root at anchor time; None when status='deferred'"
    )
    tsa_identifier: str = Field(..., description="TSA endpoint URL or identifier string")
    tsr_bytes_b64: str | None = Field(
        ..., description="RFC 3161 TimeStampResp DER bytes, base64-encoded; None if deferred"
    )
    tsa_signature_b64: str | None = Field(
        ..., description="TSA signature bytes, base64-encoded; None if deferred"
    )
    timestamped_at: datetime | None = Field(
        ..., description="TSA witness timestamp; None if deferred"
    )
    anchored_at: datetime = Field(..., description="When Forensa persisted the anchor row")

    @field_validator("anchor_date", "anchored_at")
    @classmethod
    def _tz_aware_required(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware (UTC)")
        return v

    @field_validator("timestamped_at")
    @classmethod
    def _tz_aware_optional(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError("timestamped_at must be timezone-aware (UTC) when present")
        return v

    @field_validator("root_hash")
    @classmethod
    def _root_hash_hex(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if len(v) != 64:
            raise ValueError("root_hash must be 64 hex chars when present")
        if not all(c in "0123456789abcdef" for c in v):
            raise ValueError("root_hash must be lowercase hex when present")
        return v

    @classmethod
    def from_anchor_row(cls, row: Any) -> AnchorEvidence:
        """Build AnchorEvidence from a TimestampAnchorRow.

        Accepts any object exposing the seven anchor attributes (id,
        anchor_date, status, root_hash, tsa_identifier, tsr_bytes,
        tsa_signature, timestamped_at, anchored_at). Used by
        apps/api/routes/evidence.py at request time and by tests that
        want a deterministic anchor without going through the DB.
        """
        import base64 as _b64

        tsr_bytes = getattr(row, "tsr_bytes", None)
        tsa_signature = getattr(row, "tsa_signature", None)
        return cls(
            anchor_id=row.id,
            anchor_date=row.anchor_date,
            status=row.status,
            root_hash=row.root_hash,
            tsa_identifier=row.tsa_identifier,
            tsr_bytes_b64=_b64.b64encode(tsr_bytes).decode("ascii") if tsr_bytes else None,
            tsa_signature_b64=(
                _b64.b64encode(tsa_signature).decode("ascii") if tsa_signature else None
            ),
            timestamped_at=row.timestamped_at,
            anchored_at=row.anchored_at,
        )


class EvidencePackHeader(BaseModel):
    """Pack metadata; what was exported, by whom, when, over which window."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pack_id: UUID = Field(..., description="UUID of this evidence pack")
    tenant_id: UUID = Field(..., description="Tenant whose evidence this is")
    generated_at: datetime = Field(..., description="UTC timestamp when pack was assembled")
    scope_start: datetime = Field(..., description="Inclusive start of receipts window")
    scope_end: datetime = Field(..., description="Inclusive end of receipts window")
    receipt_count: int = Field(..., ge=0, description="Number of receipts in this pack")

    @field_validator("generated_at", "scope_start", "scope_end")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware (UTC)")
        return v


class ReceiptEvidenceItem(BaseModel):
    """One Receipt as it appears inside an evidence pack.

    Includes the chain-verification fields a regulator needs to independently
    replay: sequence, prev_receipt_hash, payload_hash, receipt_hash, signature.
    The signature is base64-encoded (web-safe).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    tenant_id: UUID
    event_id: UUID
    policy_bundle_id: UUID
    policy_snapshot_id: UUID
    sequence: int = Field(..., ge=0)
    prev_receipt_hash: str | None
    payload_hash: str = Field(..., min_length=64, max_length=64)
    receipt_hash: str = Field(..., min_length=64, max_length=64)
    signature_b64: str = Field(..., description="Ed25519 signature, base64-encoded")
    signed_at: datetime

    @field_validator("signed_at")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("signed_at must be timezone-aware (UTC)")
        return v

    @field_validator("payload_hash", "receipt_hash")
    @classmethod
    def _is_hex(cls, v: str) -> str:
        if not all(c in "0123456789abcdef" for c in v):
            raise ValueError("hash must be lowercase hex")
        return v


class ProvActivity(BaseModel):
    """One PROV-O Activity node representing how a receipt was generated."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    activity_type: Literal["prov:Activity"] = "prov:Activity"
    id: str = Field(..., description="IRI for this activity (urn:forensa:activity:<uuid>)")
    used_event: str = Field(..., description="prov:used - the event IRI consumed")
    used_policy_snapshot: str = Field(
        ..., description="prov:used - the policy snapshot IRI consumed"
    )
    generated_receipt: str = Field(..., description="prov:generated - the receipt IRI produced")
    started_at: datetime
    ended_at: datetime

    @field_validator("started_at", "ended_at")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("PROV-O timestamps must be timezone-aware")
        return v


class EvidencePack(BaseModel):
    """Full JSON-LD evidence pack with PROV-O lineage block.

    Wire form starts with @context binding the namespaces; receipts and activities
    are the two payload arrays. root_hash binds the canonical JSON of
    (header, sorted receipts, sorted activities, anchor) so any tamper is detectable.

    The optional ``anchor`` field (CP9.23) carries the day's RFC 3161 TSA
    proof when the pack's scope window includes an anchored day; when
    None, the pack omits the anchor from root_hash binding (legacy /
    pre-anchored-day shape).
    """

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    context: str = Field(default=JSONLD_CONTEXT, alias="@context")
    pack_type: Literal["forensa:EvidencePack"] = Field(
        default="forensa:EvidencePack", alias="@type"
    )
    header: EvidencePackHeader
    receipts: list[ReceiptEvidenceItem]
    activities: list[ProvActivity]
    anchor: AnchorEvidence | None = Field(
        default=None,
        description=(
            "Optional RFC 3161 TSA anchor binding the day's chain root. Bound "
            "into root_hash when present; omitted from bind when None."
        ),
    )
    root_hash: str = Field(..., min_length=64, max_length=64)

    @field_validator("root_hash")
    @classmethod
    def _root_hex(cls, v: str) -> str:
        if not all(c in "0123456789abcdef" for c in v):
            raise ValueError("root_hash must be lowercase hex")
        return v

    @field_validator("receipts")
    @classmethod
    def _receipts_sorted_asc(cls, v: list[ReceiptEvidenceItem]) -> list[ReceiptEvidenceItem]:
        if v:
            seqs = [r.sequence for r in v]
            if seqs != sorted(seqs):
                raise ValueError("receipts must be sorted by sequence ASC")
        return v

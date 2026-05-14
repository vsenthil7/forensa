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
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

JSONLD_CONTEXT = "https://forensa.dev/ld/v1"
PROV_NS = "http://www.w3.org/ns/prov#"
FORENSA_NS = "https://forensa.dev/ns#"


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
    (header, sorted receipts, sorted activities) so any tamper is detectable.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    context: str = Field(default=JSONLD_CONTEXT, alias="@context")
    pack_type: Literal["forensa:EvidencePack"] = Field(
        default="forensa:EvidencePack", alias="@type"
    )
    header: EvidencePackHeader
    receipts: list[ReceiptEvidenceItem]
    activities: list[ProvActivity]
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

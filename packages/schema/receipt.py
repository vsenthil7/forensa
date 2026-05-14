"""Receipt domain model.

A Receipt is the immutable, cryptographically-signed evidence record produced
for every agent action. Contains: event reference, policy snapshot pointer,
Merkle position, signature, timestamps.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

_HEX = "0123456789abcdef"
_SHA256_LEN = 64
_ED25519_SIG_LEN = 64  # raw bytes


class Receipt(BaseModel):
    """An immutable, signed Receipt for a single agent event."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True, extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    event_id: UUID
    policy_bundle_id: UUID
    sequence: int = Field(..., ge=0, description="Per-tenant append-only sequence number")
    prev_receipt_hash: str | None = Field(
        default=None,
        description="SHA-256 hex of the previous Receipt in chain (None for first)",
    )
    payload_hash: str = Field(
        ...,
        description="SHA-256 hex of canonicalised event payload",
    )
    receipt_hash: str = Field(
        ...,
        description="SHA-256 hex of this Receipt body (binds prev + payload + meta)",
    )
    signature: bytes = Field(
        ...,
        description="Ed25519 signature over receipt_hash by TENANT key, raw 64 bytes",
    )
    agent_signature: bytes | None = Field(
        default=None,
        description=(
            "Ed25519 signature over receipt_hash by AGENT key, raw 64 bytes."
            " CP9.18 / BR-02: closes the Enterprise-Grade Review 3.10 finding"
            " 'No agent signature path. BR-02 (dual signature) is unmet'."
            " NULL is permitted for receipts persisted before alembic 0006"
            " (backwards compatibility). All new Receipts MUST have one."
        ),
    )
    signed_at: datetime

    @field_validator("prev_receipt_hash")
    @classmethod
    def _validate_prev(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if len(v) != _SHA256_LEN or not all(c in _HEX for c in v):
            raise ValueError("prev_receipt_hash must be 64-char lowercase hex if set")
        return v

    @field_validator("payload_hash", "receipt_hash")
    @classmethod
    def _validate_hash(cls, v: str) -> str:
        if len(v) != _SHA256_LEN or not all(c in _HEX for c in v):
            raise ValueError("hash field must be 64-char lowercase hex (SHA-256)")
        return v

    @field_validator("signature")
    @classmethod
    def _validate_sig_length(cls, v: bytes) -> bytes:
        if len(v) != _ED25519_SIG_LEN:
            raise ValueError(f"signature must be {_ED25519_SIG_LEN} bytes (Ed25519), got {len(v)}")
        return v

    @field_validator("agent_signature")
    @classmethod
    def _validate_agent_sig_length(cls, v: bytes | None) -> bytes | None:
        if v is None:
            return None
        if len(v) != _ED25519_SIG_LEN:
            raise ValueError(
                f"agent_signature must be {_ED25519_SIG_LEN} bytes (Ed25519), got {len(v)}"
            )
        return v

    @field_validator("signed_at")
    @classmethod
    def _require_tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("signed_at must be timezone-aware (UTC)")
        return v

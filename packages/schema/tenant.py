"""Tenant domain model.

A tenant is a logical isolation boundary for data, receipts,
and cryptographic signing keys. One tenant = one Ed25519 signing keypair.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$")


class Tenant(BaseModel):
    """A Forensa tenant."""

    model_config = ConfigDict(
        frozen=True,
        str_strip_whitespace=True,
        extra="forbid",
    )

    id: UUID = Field(default_factory=uuid4)
    slug: str = Field(
        ...,
        description="URL-safe identifier, e.g. 'acme-emea'.",
        min_length=3,
        max_length=63,
    )
    display_name: str = Field(..., min_length=1, max_length=200)
    signing_key_id: str = Field(
        ...,
        description="Reference to the Ed25519 key row in the key store.",
        min_length=1,
        max_length=128,
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    @field_validator("slug")
    @classmethod
    def _validate_slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError(
                "tenant slug must be lowercase alphanumeric + hyphens, "
                "start and end with alphanumeric, 3-63 chars"
            )
        return v

    @field_validator("created_at")
    @classmethod
    def _require_tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("created_at must be timezone-aware (UTC)")
        return v

    def as_identity(self) -> str:
        """Stable identity string for logging/HTTP headers."""
        return f"tenant:{self.slug}"

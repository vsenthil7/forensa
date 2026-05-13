"""Policy bundle domain model.

A policy bundle is a frozen, versioned set of enforcement rules any agent
action gets evaluated against. Policy version is part of every Receipt.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SEMVER_RE = re.compile(r"^\d+(\.\d+)*$")
_BUNDLE_HASH_LEN = 64


class PolicyBundle(BaseModel):
    """A frozen, versioned policy bundle bound to receipts."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True, extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    version: str = Field(..., max_length=64)
    content_hash: str = Field(...)
    content: dict[str, Any] = Field(...)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("version")
    @classmethod
    def _validate_version(cls, v: str) -> str:
        if not _SEMVER_RE.match(v):
            raise ValueError("version must be dotted decimal")
        return v

    @field_validator("content_hash")
    @classmethod
    def _validate_hash(cls, v: str) -> str:
        if len(v) != 64 or not all(c in "0123456789abcdef" for c in v):
            raise ValueError("content_hash must be 64-char lowercase hex (SHA-256)")
        return v

    @field_validator("created_at")
    @classmethod
    def _require_tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("created_at must be timezone-aware (UTC)")
        return v

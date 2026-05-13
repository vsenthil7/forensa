"""Agent domain model.

An agent is an AI agent (LangGraph node, MCP client, etc) whose actions
are recorded into the Forensa evidence ledger. One agent = one identity key.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

_AGENT_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-_]{0,61}[a-z0-9]$")


class AgentStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    RETIRED = "retired"


class Agent(BaseModel):
    """An AI agent registered to a tenant."""

    model_config = ConfigDict(
        frozen=True,
        str_strip_whitespace=True,
        extra="forbid",
        use_enum_values=True,
    )

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    slug: str = Field(..., min_length=3, max_length=63)
    display_name: str = Field(..., min_length=1, max_length=200)
    identity_public_key: bytes = Field(
        ...,
        description="Ed25519 public key, 32 raw bytes.",
    )
    status: AgentStatus = Field(default=AgentStatus.ACTIVE)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    @field_validator("slug")
    @classmethod
    def _validate_slug(cls, v: str) -> str:
        if not _AGENT_SLUG_RE.match(v):
            raise ValueError(
                "agent slug must be lowercase alphanumeric + hyphens/underscores, "
                "start/end with alphanumeric, 3-63 chars"
            )
        return v

    @field_validator("identity_public_key")
    @classmethod
    def _validate_key_length(cls, v: bytes) -> bytes:
        if len(v) != 32:
            raise ValueError(f"identity_public_key must be 32 bytes, got {len(v)}")
        return v

    @field_validator("created_at")
    @classmethod
    def _require_tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("created_at must be timezone-aware (UTC)")
        return v

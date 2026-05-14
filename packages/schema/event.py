"""Event domain model.

An event is a single action taken by an agent: tool call, LLM invocation,
auth decision, etc. Normalised from OTel GenAI OTLP payloads.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EventKind(str, Enum):
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    LLM_INVOCATION = "llm_invocation"
    AUTH_DECISION = "auth_decision"
    POLICY_VERDICT = "policy_verdict"
    AGENT_MESSAGE = "agent_message"
    RESOURCE_ACCESS = "resource_access"


class Event(BaseModel):
    """A normalised agent event, pre-ledger.

    No Merkle hash yet; this is the input shape accepted by POST /v1/events.
    """

    model_config = ConfigDict(
        frozen=True,
        str_strip_whitespace=True,
        extra="forbid",
        use_enum_values=True,
    )

    id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    agent_id: UUID
    trace_id: str = Field(
        ...,
        description="W3C trace id (hex, 32 chars).",
        min_length=32,
        max_length=32,
    )
    span_id: str = Field(
        ...,
        description="W3C span id (hex, 16 chars).",
        min_length=16,
        max_length=16,
    )
    parent_span_id: str | None = Field(default=None)
    kind: EventKind
    occurred_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)
    reasoning: str | None = Field(
        default=None,
        description=(
            "Agent's chain-of-thought or rationale, if captured. Populated only"
            " from explicit ``forensa.reasoning`` OTel attribute. NOT a fallback"
            " for ``gen_ai.response.text`` (which is the model's output, not its"
            " reasoning - see ``output`` field). [CP9.9]"
        ),
    )
    output: str | None = Field(
        default=None,
        description=(
            "The model's response text, captured from ``gen_ai.response.text``."
            " Distinct from ``reasoning``: reasoning is the agent's rationale"
            " for taking an action; output is the textual result the model"
            " produced. [CP9.9 - NEW-P9.8.21]"
        ),
    )
    policy_version: str | None = Field(
        default=None,
        description="Version of the policy bundle active at occurrence time.",
        max_length=64,
    )
    policy_verdict: str | None = Field(
        default=None,
        description="E.g. 'allow', 'deny', 'allow_with_conditions'.",
        max_length=64,
    )

    @field_validator("trace_id", "span_id")
    @classmethod
    def _validate_hex(cls, v: str) -> str:
        if not all(c in "0123456789abcdef" for c in v):
            raise ValueError("trace_id/span_id must be lowercase hex")
        return v

    @field_validator("parent_span_id")
    @classmethod
    def _validate_parent_span(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if len(v) != 16 or not all(c in "0123456789abcdef" for c in v):
            raise ValueError("parent_span_id must be 16-char lowercase hex if set")
        return v

    @field_validator("occurred_at")
    @classmethod
    def _require_tz(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware (UTC)")
        return v

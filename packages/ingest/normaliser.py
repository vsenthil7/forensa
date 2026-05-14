"""OTel GenAI span -> Forensa Event normaliser.

Maps OpenTelemetry GenAI-semantic-convention spans into the internal
Event schema. Pure function, no I/O. Caller supplies tenant_id and
agent_id (resolved from OTel resource attributes or an auth gate upstream).

Reference: https://opentelemetry.io/docs/specs/semconv/gen-ai/
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from packages.schema.event import Event, EventKind

# Mapping from OTel GenAI span operation type to internal EventKind.
# https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-spans/
_GENAI_OP_TO_KIND: dict[str, EventKind] = {
    "chat": EventKind.LLM_INVOCATION,
    "text_completion": EventKind.LLM_INVOCATION,
    "embeddings": EventKind.LLM_INVOCATION,
    "execute_tool": EventKind.TOOL_CALL,
    "tool_call": EventKind.TOOL_CALL,
    "tool_result": EventKind.TOOL_RESULT,
}


class NormaliserError(ValueError):
    """Raised when an OTel span cannot be normalised."""


def _coerce_hex(value: str, expected_len: int, field_name: str) -> str:
    """Validate and lowercase a hex string of expected length."""
    if not isinstance(value, str):
        raise NormaliserError(f"{field_name} must be a string, got {type(value).__name__}")
    lower = value.lower()
    if len(lower) != expected_len:
        raise NormaliserError(
            f"{field_name} must be {expected_len} lowercase hex chars, got {len(lower)}"
        )
    if not all(c in "0123456789abcdef" for c in lower):
        raise NormaliserError(f"{field_name} contains non-hex character: {value!r}")
    return lower


def _parse_occurred_at(raw: Any) -> datetime:
    """Accept ISO-8601 string or epoch nanoseconds (int) and return tz-aware UTC."""
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            raise NormaliserError("occurred_at datetime must be timezone-aware")
        return raw
    if isinstance(raw, int):
        return datetime.fromtimestamp(raw / 1_000_000_000, tz=UTC)
    if isinstance(raw, str):
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise NormaliserError(f"occurred_at string lacks timezone: {raw!r}")
        return dt
    raise NormaliserError(f"occurred_at unsupported type: {type(raw).__name__}")


def _resolve_kind(attributes: Mapping[str, Any]) -> EventKind:
    """Determine EventKind from OTel attributes.

    Precedence: explicit forensa.event.kind override beats gen_ai.operation.name
    beats fallback to AGENT_MESSAGE.
    """
    forensa_kind = attributes.get("forensa.event.kind")
    if forensa_kind is not None:
        try:
            return EventKind(forensa_kind)
        except ValueError as exc:
            raise NormaliserError(
                f"forensa.event.kind value {forensa_kind!r} is not a valid EventKind"
            ) from exc

    op_name = attributes.get("gen_ai.operation.name")
    if op_name is not None and op_name in _GENAI_OP_TO_KIND:
        return _GENAI_OP_TO_KIND[op_name]

    return EventKind.AGENT_MESSAGE


def normalise_otel_span(
    span: Mapping[str, Any],
    *,
    tenant_id: UUID,
    agent_id: UUID,
    occurred_at: Any | None = None,
) -> Event:
    """Convert an OTel GenAI span (dict shape) into a validated Event.

    Required keys in span:
        trace_id: 32-char hex string
        span_id: 16-char hex string

    Optional keys:
        parent_span_id: 16-char hex string
        attributes: Mapping[str, Any]
        start_time_unix_nano OR start_time (ISO-8601)

    Raises NormaliserError on shape problems before Event validation runs.
    """
    if "trace_id" not in span:
        raise NormaliserError("span is missing trace_id")
    if "span_id" not in span:
        raise NormaliserError("span is missing span_id")

    trace_id = _coerce_hex(span["trace_id"], 32, "trace_id")
    span_id = _coerce_hex(span["span_id"], 16, "span_id")

    parent_raw = span.get("parent_span_id")
    parent_span_id = _coerce_hex(parent_raw, 16, "parent_span_id") if parent_raw else None

    attributes = span.get("attributes") or {}
    if not isinstance(attributes, Mapping):
        raise NormaliserError("attributes must be a mapping")

    kind = _resolve_kind(attributes)

    if occurred_at is not None:
        occ = _parse_occurred_at(occurred_at)
    elif "start_time_unix_nano" in span:
        occ = _parse_occurred_at(span["start_time_unix_nano"])
    elif "start_time" in span:
        occ = _parse_occurred_at(span["start_time"])
    else:
        raise NormaliserError("span missing start_time_unix_nano or start_time")

    payload = dict(attributes)
    # CP9.9 / NEW-P9.8.21: ``reasoning`` is the agent's rationale and is
    # populated ONLY from the explicit ``forensa.reasoning`` attribute. The
    # previous fallback to ``gen_ai.response.text`` was wrong: response.text
    # is the model's *output*, not its *reasoning*. They are different things
    # and conflating them would mislead investigators.
    reasoning = payload.pop("forensa.reasoning", None)
    output = payload.pop("gen_ai.response.text", None)
    policy_version = payload.pop("forensa.policy.version", None)
    policy_verdict = payload.pop("forensa.policy.verdict", None)

    return Event(
        tenant_id=tenant_id,
        agent_id=agent_id,
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        kind=kind,
        occurred_at=occ,
        payload=payload,
        reasoning=reasoning,
        output=output,
        policy_version=policy_version,
        policy_verdict=policy_verdict,
    )

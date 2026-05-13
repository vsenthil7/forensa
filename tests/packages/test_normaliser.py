"""Tests for OTel GenAI span normaliser."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from packages.ingest.normaliser import NormaliserError, normalise_otel_span
from packages.schema.event import EventKind

TENANT = uuid4()
AGENT = uuid4()


def _good_span(**over):
    base = {
        "trace_id": "a" * 32,
        "span_id": "b" * 16,
        "start_time_unix_nano": 1_700_000_000_000_000_000,
        "attributes": {"gen_ai.operation.name": "chat"},
    }
    base.update(over)
    return base


def test_minimal_chat_span_maps_to_llm_invocation():
    ev = normalise_otel_span(_good_span(), tenant_id=TENANT, agent_id=AGENT)
    assert ev.kind == EventKind.LLM_INVOCATION.value
    assert ev.trace_id == "a" * 32
    assert ev.span_id == "b" * 16
    assert ev.parent_span_id is None
    assert ev.tenant_id == TENANT
    assert ev.agent_id == AGENT
    assert ev.occurred_at.tzinfo is not None


@pytest.mark.parametrize(
    "op_name,expected_kind",
    [
        ("chat", EventKind.LLM_INVOCATION),
        ("text_completion", EventKind.LLM_INVOCATION),
        ("embeddings", EventKind.LLM_INVOCATION),
        ("execute_tool", EventKind.TOOL_CALL),
        ("tool_call", EventKind.TOOL_CALL),
        ("tool_result", EventKind.TOOL_RESULT),
    ],
)
def test_genai_operation_name_to_kind(op_name, expected_kind):
    span = _good_span(attributes={"gen_ai.operation.name": op_name})
    ev = normalise_otel_span(span, tenant_id=TENANT, agent_id=AGENT)
    assert ev.kind == expected_kind.value


def test_unknown_operation_name_falls_back_to_agent_message():
    span = _good_span(attributes={"gen_ai.operation.name": "nothingknown"})
    ev = normalise_otel_span(span, tenant_id=TENANT, agent_id=AGENT)
    assert ev.kind == EventKind.AGENT_MESSAGE.value


def test_forensa_event_kind_override_takes_precedence():
    span = _good_span(
        attributes={
            "gen_ai.operation.name": "chat",
            "forensa.event.kind": "auth_decision",
        }
    )
    ev = normalise_otel_span(span, tenant_id=TENANT, agent_id=AGENT)
    assert ev.kind == EventKind.AUTH_DECISION.value


def test_invalid_forensa_event_kind_raises():
    span = _good_span(attributes={"forensa.event.kind": "not_a_valid_kind"})
    with pytest.raises(NormaliserError, match="not a valid EventKind"):
        normalise_otel_span(span, tenant_id=TENANT, agent_id=AGENT)


def test_parent_span_id_passed_through():
    span = _good_span(parent_span_id="c" * 16)
    ev = normalise_otel_span(span, tenant_id=TENANT, agent_id=AGENT)
    assert ev.parent_span_id == "c" * 16


def test_missing_trace_id_raises():
    span = _good_span()
    del span["trace_id"]
    with pytest.raises(NormaliserError, match="missing trace_id"):
        normalise_otel_span(span, tenant_id=TENANT, agent_id=AGENT)


def test_missing_span_id_raises():
    span = _good_span()
    del span["span_id"]
    with pytest.raises(NormaliserError, match="missing span_id"):
        normalise_otel_span(span, tenant_id=TENANT, agent_id=AGENT)


def test_missing_start_time_raises():
    span = _good_span()
    del span["start_time_unix_nano"]
    with pytest.raises(NormaliserError, match="start_time_unix_nano or start_time"):
        normalise_otel_span(span, tenant_id=TENANT, agent_id=AGENT)


def test_explicit_occurred_at_overrides_span_time():
    fixed = datetime(2026, 5, 13, 10, 0, tzinfo=UTC)
    span = _good_span()
    ev = normalise_otel_span(span, tenant_id=TENANT, agent_id=AGENT, occurred_at=fixed)
    assert ev.occurred_at == fixed


def test_start_time_iso_string_accepted():
    span = _good_span()
    del span["start_time_unix_nano"]
    span["start_time"] = "2026-05-13T10:00:00+00:00"
    ev = normalise_otel_span(span, tenant_id=TENANT, agent_id=AGENT)
    assert ev.occurred_at.year == 2026
    assert ev.occurred_at.hour == 10


def test_start_time_iso_string_with_z_suffix():
    span = _good_span()
    del span["start_time_unix_nano"]
    span["start_time"] = "2026-05-13T10:00:00Z"
    ev = normalise_otel_span(span, tenant_id=TENANT, agent_id=AGENT)
    assert ev.occurred_at.tzinfo is not None


def test_naive_iso_string_rejected():
    span = _good_span()
    del span["start_time_unix_nano"]
    span["start_time"] = "2026-05-13T10:00:00"
    with pytest.raises(NormaliserError, match="lacks timezone"):
        normalise_otel_span(span, tenant_id=TENANT, agent_id=AGENT)


def test_naive_datetime_rejected():
    fixed = datetime(2026, 5, 13, 10, 0)  # no tzinfo
    with pytest.raises(NormaliserError, match="must be timezone-aware"):
        normalise_otel_span(_good_span(), tenant_id=TENANT, agent_id=AGENT, occurred_at=fixed)


def test_invalid_occurred_at_type_rejected():
    with pytest.raises(NormaliserError, match="unsupported type"):
        normalise_otel_span(_good_span(), tenant_id=TENANT, agent_id=AGENT, occurred_at=12.5)


@pytest.mark.parametrize(
    "bad_trace",
    ["", "a" * 31, "a" * 33, "g" * 32],
)
def test_bad_trace_id_rejected(bad_trace):
    with pytest.raises(NormaliserError):
        normalise_otel_span(_good_span(trace_id=bad_trace), tenant_id=TENANT, agent_id=AGENT)


@pytest.mark.parametrize(
    "bad_span",
    ["", "b" * 15, "b" * 17, "z" * 16],
)
def test_bad_span_id_rejected(bad_span):
    with pytest.raises(NormaliserError):
        normalise_otel_span(_good_span(span_id=bad_span), tenant_id=TENANT, agent_id=AGENT)


def test_non_string_trace_id_rejected():
    with pytest.raises(NormaliserError, match="must be a string"):
        normalise_otel_span(_good_span(trace_id=12345), tenant_id=TENANT, agent_id=AGENT)


def test_uppercase_trace_id_normalised_to_lowercase():
    # 32-char string with mixed case but all valid hex chars
    span = _good_span(trace_id="0123456789ABCDEF0123456789ABCDEF")
    ev = normalise_otel_span(span, tenant_id=TENANT, agent_id=AGENT)
    assert ev.trace_id == "0123456789abcdef0123456789abcdef"


def test_attributes_not_mapping_rejected():
    span = _good_span(attributes=["not_a_mapping"])
    with pytest.raises(NormaliserError, match="must be a mapping"):
        normalise_otel_span(span, tenant_id=TENANT, agent_id=AGENT)


def test_no_attributes_defaults_to_agent_message():
    span = _good_span()
    del span["attributes"]
    ev = normalise_otel_span(span, tenant_id=TENANT, agent_id=AGENT)
    assert ev.kind == EventKind.AGENT_MESSAGE.value
    assert ev.payload == {}


def test_forensa_reasoning_extracted_to_event_field():
    span = _good_span(
        attributes={
            "gen_ai.operation.name": "chat",
            "forensa.reasoning": "I chose this because the user asked",
        }
    )
    ev = normalise_otel_span(span, tenant_id=TENANT, agent_id=AGENT)
    assert ev.reasoning == "I chose this because the user asked"
    assert "forensa.reasoning" not in ev.payload


def test_genai_response_text_falls_back_to_reasoning():
    span = _good_span(
        attributes={
            "gen_ai.operation.name": "chat",
            "gen_ai.response.text": "The answer is 42",
        }
    )
    ev = normalise_otel_span(span, tenant_id=TENANT, agent_id=AGENT)
    assert ev.reasoning == "The answer is 42"


def test_policy_fields_extracted_from_attributes():
    span = _good_span(
        attributes={
            "gen_ai.operation.name": "chat",
            "forensa.policy.version": "2.1.0",
            "forensa.policy.verdict": "allow",
        }
    )
    ev = normalise_otel_span(span, tenant_id=TENANT, agent_id=AGENT)
    assert ev.policy_version == "2.1.0"
    assert ev.policy_verdict == "allow"
    assert "forensa.policy.version" not in ev.payload
    assert "forensa.policy.verdict" not in ev.payload


def test_payload_preserves_other_attributes():
    span = _good_span(
        attributes={
            "gen_ai.operation.name": "chat",
            "gen_ai.request.model": "gemini-2.5-pro",
            "gen_ai.usage.input_tokens": 142,
        }
    )
    ev = normalise_otel_span(span, tenant_id=TENANT, agent_id=AGENT)
    assert ev.payload["gen_ai.request.model"] == "gemini-2.5-pro"
    assert ev.payload["gen_ai.usage.input_tokens"] == 142


def test_invalid_parent_span_id_rejected():
    span = _good_span(parent_span_id="tooshort")
    with pytest.raises(NormaliserError, match="16 lowercase"):
        normalise_otel_span(span, tenant_id=TENANT, agent_id=AGENT)

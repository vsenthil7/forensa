"""Tests for Event schema model — 100% branch coverage."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from packages.schema.event import Event, EventKind


def _good(**over):
    base = dict(
        tenant_id=uuid4(),
        agent_id=uuid4(),
        trace_id="a" * 32,
        span_id="b" * 16,
        kind=EventKind.TOOL_CALL,
        occurred_at=datetime(2026, 5, 13, 8, 0, tzinfo=UTC),
    )
    base.update(over)
    return base


def test_event_minimal_valid():
    e = Event(**_good())
    assert e.trace_id == "a" * 32
    assert e.span_id == "b" * 16
    assert e.kind == "tool_call"
    assert e.payload == {}
    assert e.parent_span_id is None
    assert e.reasoning is None
    assert e.policy_version is None
    assert e.policy_verdict is None


def test_event_all_optional_fields_set():
    e = Event(
        parent_span_id="c" * 16,
        payload={"tool": "search", "args": {"q": "foo"}},
        reasoning="The user asked about X, so I called search.",
        policy_version="1.4.2",
        policy_verdict="allow",
        **_good(),
    )
    assert e.parent_span_id == "c" * 16
    assert e.payload["tool"] == "search"
    assert e.policy_version == "1.4.2"
    assert e.policy_verdict == "allow"


@pytest.mark.parametrize("kind", list(EventKind))
def test_event_all_kinds_accepted(kind):
    e = Event(**_good(kind=kind))
    assert e.kind == kind.value


@pytest.mark.parametrize(
    "bad_trace",
    ["", "a" * 31, "a" * 33, "A" * 32, "g" * 32, "z" * 32, "0123" * 7 + "xyz!"],
)
def test_event_rejects_bad_trace_id(bad_trace):
    with pytest.raises(ValidationError):
        Event(**_good(trace_id=bad_trace))


@pytest.mark.parametrize("bad_span", ["", "b" * 15, "b" * 17, "B" * 16, "g" * 16, "z" * 16])
def test_event_rejects_bad_span_id(bad_span):
    with pytest.raises(ValidationError):
        Event(**_good(span_id=bad_span))


@pytest.mark.parametrize("bad_parent", ["", "c" * 15, "c" * 17, "C" * 16, "g" * 16])
def test_event_rejects_bad_parent_span_id(bad_parent):
    with pytest.raises(ValidationError):
        Event(parent_span_id=bad_parent, **_good())


def test_event_accepts_none_parent_span_id():
    e = Event(parent_span_id=None, **_good())
    assert e.parent_span_id is None


def test_event_rejects_naive_occurred_at():
    with pytest.raises(ValidationError) as exc:
        Event(**_good(occurred_at=datetime(2026, 5, 13, 8, 0)))
    assert "timezone-aware" in str(exc.value)


def test_event_frozen():
    e = Event(**_good())
    with pytest.raises(ValidationError):
        e.trace_id = "x" * 32


def test_event_forbids_extra_fields():
    with pytest.raises(ValidationError):
        Event(evil="data", **_good())


def test_event_id_defaults_unique():
    e1 = Event(**_good())
    e2 = Event(**_good())
    assert e1.id != e2.id

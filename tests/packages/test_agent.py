"""Tests for Agent schema model — 100% branch coverage."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from packages.schema.agent import Agent, AgentStatus


def _good_kwargs(**over):
    base = dict(
        tenant_id=uuid4(),
        slug="legal-bot-1",
        display_name="Legal Bot 1",
        identity_public_key=b"\x01" * 32,
    )
    base.update(over)
    return base


def test_agent_minimal_valid():
    a = Agent(**_good_kwargs())
    assert a.slug == "legal-bot-1"
    assert a.status == "active"
    assert a.identity_public_key == b"\x01" * 32
    assert a.created_at.tzinfo is not None


def test_agent_status_enum_values():
    for s in ("active", "suspended", "retired"):
        a = Agent(**_good_kwargs(status=AgentStatus(s)))
        assert a.status == s


def test_agent_default_status_is_active():
    a = Agent(**_good_kwargs())
    assert a.status == AgentStatus.ACTIVE.value


def test_agent_explicit_uuid_and_timestamp():
    aid = uuid4()
    ts = datetime(2026, 5, 13, 8, 0, tzinfo=timezone.utc)
    a = Agent(id=aid, created_at=ts, **_good_kwargs())
    assert a.id == aid
    assert a.created_at == ts


@pytest.mark.parametrize(
    "bad_slug",
    ["A", "AB", "ab", "-abc", "abc-", "ab c", "ab.c", "ab/cd", "ab!c", "a" * 64],
)
def test_agent_rejects_invalid_slug(bad_slug):
    with pytest.raises(ValidationError):
        Agent(**_good_kwargs(slug=bad_slug))


def test_agent_accepts_underscore_slug():
    a = Agent(**_good_kwargs(slug="legal_bot_1"))
    assert a.slug == "legal_bot_1"


@pytest.mark.parametrize("bad_len", [0, 1, 16, 31, 33, 64])
def test_agent_rejects_wrong_key_length(bad_len):
    with pytest.raises(ValidationError) as exc:
        Agent(**_good_kwargs(identity_public_key=b"\x02" * bad_len))
    assert "32 bytes" in str(exc.value)


def test_agent_rejects_naive_created_at():
    with pytest.raises(ValidationError) as exc:
        Agent(created_at=datetime(2026, 5, 13, 8, 0), **_good_kwargs())
    assert "timezone-aware" in str(exc.value)


def test_agent_frozen():
    a = Agent(**_good_kwargs())
    with pytest.raises(ValidationError):
        a.slug = "other"


def test_agent_forbids_extra_fields():
    with pytest.raises(ValidationError):
        Agent(evil="data", **_good_kwargs())

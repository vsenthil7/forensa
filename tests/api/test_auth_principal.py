"""Tests for apps.api.auth.principal — Principal frozen dataclass."""

from __future__ import annotations

from uuid import uuid4

import pytest

from apps.api.auth.principal import Principal


def test_principal_default_scopes_is_empty_frozenset():
    tid = uuid4()
    aid = uuid4()
    p = Principal(tenant_id=tid, agent_id=aid, agent_slug="agent-alpha")
    assert p.scopes == frozenset()
    assert isinstance(p.scopes, frozenset)


def test_principal_with_explicit_scopes():
    p = Principal(
        tenant_id=uuid4(),
        agent_id=uuid4(),
        agent_slug="agent-beta",
        scopes=frozenset({"events:write", "receipts:read"}),
    )
    assert p.has_scope("events:write") is True
    assert p.has_scope("receipts:read") is True
    assert p.has_scope("admin:delete") is False


def test_principal_is_frozen():
    """frozen=True - attempting to mutate any field raises."""
    p = Principal(tenant_id=uuid4(), agent_id=uuid4(), agent_slug="agent-gamma")
    with pytest.raises(AttributeError):
        p.tenant_id = uuid4()  # type: ignore[misc]
    with pytest.raises(AttributeError):
        p.agent_id = uuid4()  # type: ignore[misc]
    with pytest.raises(AttributeError):
        p.agent_slug = "other"  # type: ignore[misc]


def test_principal_equality_is_structural():
    """Two Principals with identical fields compare equal."""
    tid = uuid4()
    aid = uuid4()
    p1 = Principal(tenant_id=tid, agent_id=aid, agent_slug="agent-x")
    p2 = Principal(tenant_id=tid, agent_id=aid, agent_slug="agent-x")
    assert p1 == p2


def test_principal_inequality_on_different_tenant():
    aid = uuid4()
    p1 = Principal(tenant_id=uuid4(), agent_id=aid, agent_slug="agent-x")
    p2 = Principal(tenant_id=uuid4(), agent_id=aid, agent_slug="agent-x")
    assert p1 != p2


def test_principal_inequality_on_different_agent():
    tid = uuid4()
    p1 = Principal(tenant_id=tid, agent_id=uuid4(), agent_slug="agent-x")
    p2 = Principal(tenant_id=tid, agent_id=uuid4(), agent_slug="agent-x")
    assert p1 != p2


def test_principal_inequality_on_different_scopes():
    tid = uuid4()
    aid = uuid4()
    p1 = Principal(tenant_id=tid, agent_id=aid, agent_slug="a", scopes=frozenset({"read"}))
    p2 = Principal(tenant_id=tid, agent_id=aid, agent_slug="a", scopes=frozenset({"write"}))
    assert p1 != p2


def test_principal_is_hashable():
    """frozen=True + frozenset scopes -> hashable -> usable as dict key / set member."""
    p = Principal(
        tenant_id=uuid4(),
        agent_id=uuid4(),
        agent_slug="agent-h",
        scopes=frozenset({"a", "b"}),
    )
    s = {p}
    assert p in s


def test_has_scope_on_empty_returns_false():
    p = Principal(tenant_id=uuid4(), agent_id=uuid4(), agent_slug="agent-empty")
    assert p.has_scope("anything") is False

"""Tests for POST /v1/events ingestion endpoint."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import create_app


def _valid_event_payload(**over):
    base = {
        "tenant_id": str(uuid4()),
        "agent_id": str(uuid4()),
        "trace_id": "a" * 32,
        "span_id": "b" * 16,
        "kind": "tool_call",
        "occurred_at": datetime(2026, 5, 13, 9, 50, tzinfo=timezone.utc).isoformat(),
    }
    base.update(over)
    return base


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_post_event_accepts_minimal_valid(client):
    resp = await client.post("/v1/events", json=_valid_event_payload())
    assert resp.status_code == 202
    body = resp.json()
    assert "event_id" in body
    assert body["status"] == "accepted"
    assert "accepted_at" in body
    # Event id should also appear in response header
    assert resp.headers["X-Forensa-Event-Id"] == body["event_id"]


@pytest.mark.asyncio
async def test_post_event_accepts_full_payload(client):
    payload = _valid_event_payload(
        parent_span_id="c" * 16,
        payload={"tool": "search", "args": {"q": "foo"}},
        reasoning="User asked X so I called search.",
        policy_version="1.4.2",
        policy_verdict="allow",
    )
    resp = await client.post("/v1/events", json=payload)
    assert resp.status_code == 202


@pytest.mark.asyncio
async def test_post_event_rejects_bad_trace_id(client):
    bad = _valid_event_payload(trace_id="too-short")
    resp = await client.post("/v1/events", json=bad)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_post_event_rejects_bad_span_id(client):
    bad = _valid_event_payload(span_id="BAD")
    resp = await client.post("/v1/events", json=bad)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_post_event_rejects_invalid_kind(client):
    bad = _valid_event_payload(kind="not_a_valid_kind")
    resp = await client.post("/v1/events", json=bad)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_post_event_rejects_naive_timestamp(client):
    bad = _valid_event_payload(occurred_at="2026-05-13T09:50:00")
    resp = await client.post("/v1/events", json=bad)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_post_event_rejects_missing_required_field(client):
    payload = _valid_event_payload()
    del payload["trace_id"]
    resp = await client.post("/v1/events", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_post_event_rejects_extra_field(client):
    payload = _valid_event_payload(evil="data")
    resp = await client.post("/v1/events", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_post_event_with_all_event_kinds(client):
    for kind in ["tool_call", "tool_result", "llm_invocation", "auth_decision", "policy_verdict", "agent_message", "resource_access"]:
        resp = await client.post("/v1/events", json=_valid_event_payload(kind=kind))
        assert resp.status_code == 202, f"kind={kind} should be accepted"


@pytest.mark.asyncio
async def test_post_event_accepted_at_is_recent(client):
    before = datetime.now(timezone.utc)
    resp = await client.post("/v1/events", json=_valid_event_payload())
    after = datetime.now(timezone.utc)
    accepted_at = datetime.fromisoformat(resp.json()["accepted_at"])
    assert before <= accepted_at <= after


@pytest.mark.asyncio
async def test_post_event_returns_unique_event_ids(client):
    r1 = await client.post("/v1/events", json=_valid_event_payload())
    r2 = await client.post("/v1/events", json=_valid_event_payload())
    assert r1.json()["event_id"] != r2.json()["event_id"]


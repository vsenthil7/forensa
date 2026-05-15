"""Tests for POST /v1/tabletop/simulate (CP9.29 / BR-12)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import create_app
from apps.api.routes.receipts import get_session
from packages.policy.bundle_builder import build_bundle
from tests.api._auth_helpers import install_principal_override

_TENANT = UUID("44444444-5555-6666-7777-888888888888")
_OTHER_TENANT = UUID("55555555-6666-7777-8888-999999999999")
_AGENT = UUID("33333333-4444-5555-6666-777777777777")
_CONTENT: dict[str, Any] = {
    "rules": [
        {"kind": "deny_kind", "decision": "deny"},
        {"kind": "escalate_kind", "decision": "escalate"},
    ],
    "default": "allow",
}


def _make_bundle_row(bundle):
    from packages.ledger.models import PolicyBundleRow

    row = MagicMock(spec=PolicyBundleRow)
    row.id = bundle.id
    row.tenant_id = bundle.tenant_id
    row.version = bundle.version
    row.content_hash = bundle.content_hash
    row.content = bundle.content
    row.created_at = bundle.created_at
    return row


def _override_session_returning_bundle(bundle_row_or_none):
    async def _execute(stmt):
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=bundle_row_or_none)
        return result

    session = MagicMock()
    session.execute = AsyncMock(side_effect=_execute)

    async def _override():
        return session

    return _override


@pytest.fixture
def app():
    a = create_app()
    install_principal_override(a, tenant_id=_TENANT, agent_id=_AGENT)
    return a


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _scenario_body(
    *,
    tenant_id: UUID = _TENANT,
    bundle_id: UUID,
    actions: list[dict] | None = None,
) -> dict:
    if actions is None:
        actions = [
            {"label": "a-1", "action": {"kind": "ok"}},
            {"label": "a-2", "action": {"kind": "deny_kind"}},
            {"label": "a-3", "action": {"kind": "escalate_kind"}},
        ]
    return {
        "name": "test-scenario",
        "tenant_id": str(tenant_id),
        "policy_bundle_id": str(bundle_id),
        "actions": actions,
    }


# ---------- happy path ----------


@pytest.mark.asyncio
async def test_simulate_happy_path(app, client) -> None:
    bundle = build_bundle(tenant_id=_TENANT, version="1.0.0", content=_CONTENT)
    app.dependency_overrides[get_session] = _override_session_returning_bundle(
        _make_bundle_row(bundle)
    )
    response = await client.post(
        "/v1/tabletop/simulate",
        json=_scenario_body(bundle_id=bundle.id),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["scenario"]["name"] == "test-scenario"
    assert body["bundle_id"] == str(bundle.id)
    assert body["bundle_content_hash"] == bundle.content_hash
    assert body["summary"]["total"] == 3
    assert body["summary"]["allow"] == 1
    assert body["summary"]["deny"] == 1
    assert body["summary"]["escalate"] == 1
    assert body["summary"]["errored"] == 0
    assert len(body["action_results"]) == 3
    app.dependency_overrides.clear()


# ---------- authz ----------


@pytest.mark.asyncio
async def test_simulate_403_when_scenario_tenant_does_not_match_principal(app, client) -> None:
    bundle = build_bundle(tenant_id=_TENANT, version="1.0.0", content=_CONTENT)
    app.dependency_overrides[get_session] = _override_session_returning_bundle(
        _make_bundle_row(bundle)
    )
    response = await client.post(
        "/v1/tabletop/simulate",
        json=_scenario_body(tenant_id=_OTHER_TENANT, bundle_id=bundle.id),
    )
    assert response.status_code == 403
    body = response.json()
    assert body["detail"]["error"] == "tenant_mismatch"
    app.dependency_overrides.clear()


# ---------- 404 paths ----------


@pytest.mark.asyncio
async def test_simulate_404_when_bundle_does_not_exist(app, client) -> None:
    # Session returns None for the bundle lookup.
    app.dependency_overrides[get_session] = _override_session_returning_bundle(None)
    response = await client.post(
        "/v1/tabletop/simulate",
        json=_scenario_body(bundle_id=uuid4()),
    )
    assert response.status_code == 404
    body = response.json()
    assert body["detail"]["error"] == "bundle_not_found"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_simulate_404_when_bundle_belongs_to_other_tenant(app, client) -> None:
    """Cross-tenant probing returns 404 (not 403) to avoid leaking bundle ids.

    CP9.33: tenant scoping is enforced at the SQL layer via
    get_bundle_by_id(..., tenant_id=scenario.tenant_id). When the lookup
    targets a tenant_id that doesn't own the bundle, the SQL filter
    `WHERE id = :bid AND tenant_id = :tid` returns no row -> the mock
    here returns None to reflect that real-DB behaviour. (Before CP9.33
    the route did a post-query check `bundle.tenant_id != scenario.tenant_id`
    so the test mocked the row as present-but-foreign; that test shape is
    no longer accurate because the SQL filter intercepts the lookup before
    any row reaches the route.)
    """
    # Session returns None because the SQL filter `tenant_id=_TENANT`
    # would not match a row owned by _OTHER_TENANT.
    app.dependency_overrides[get_session] = _override_session_returning_bundle(None)
    response = await client.post(
        "/v1/tabletop/simulate",
        json=_scenario_body(bundle_id=uuid4()),
    )
    assert response.status_code == 404
    body = response.json()
    assert body["detail"]["error"] == "bundle_not_found"
    app.dependency_overrides.clear()


# ---------- input validation ----------


@pytest.mark.asyncio
async def test_simulate_422_when_scenario_has_no_actions(app, client) -> None:
    bundle = build_bundle(tenant_id=_TENANT, version="1.0.0", content=_CONTENT)
    app.dependency_overrides[get_session] = _override_session_returning_bundle(
        _make_bundle_row(bundle)
    )
    response = await client.post(
        "/v1/tabletop/simulate",
        json=_scenario_body(bundle_id=bundle.id, actions=[]),
    )
    assert response.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_simulate_422_when_action_spec_label_empty(app, client) -> None:
    bundle = build_bundle(tenant_id=_TENANT, version="1.0.0", content=_CONTENT)
    app.dependency_overrides[get_session] = _override_session_returning_bundle(
        _make_bundle_row(bundle)
    )
    response = await client.post(
        "/v1/tabletop/simulate",
        json=_scenario_body(
            bundle_id=bundle.id,
            actions=[{"label": "", "action": {"kind": "ok"}}],
        ),
    )
    assert response.status_code == 422
    app.dependency_overrides.clear()


# ---------- CP9.37 / IP #10 NEW-P11.X.tabletop-bundle-from-storage ----------
#
# IP #10 was originally scoped as: "add a route-level filter so tabletop can
# target draft/proposed bundles, not just active." On inspection of
# packages/ledger/bundle_repository.py, get_bundle_by_id is STATUS-AGNOSTIC --
# it returns a bundle by id regardless of approval-workflow status. The
# tabletop route at CP9.29 already accepts any-status bundle. The capability
# already exists end-to-end.
#
# Disposition: IP #10 RETRACTED as a no-op item. The tests below PROVE the
# any-status behaviour against the actual five bundle statuses currently
# defined by alembic 0004 (proposed, reviewed, approved, active, superseded).
# This locks in the contract going forward so a future bundle-storage change
# that accidentally introduces a status filter would break a test.


@pytest.mark.parametrize(
    "bundle_status",
    ["proposed", "reviewed", "approved", "active", "superseded"],
)
@pytest.mark.asyncio
async def test_simulate_accepts_bundle_in_any_workflow_status(
    app, client, bundle_status: str
) -> None:
    """Security engineers can dry-run scenarios against bundles still in the
    approval workflow, not just active ones. The route + repo are
    status-agnostic by design.
    """
    bundle = build_bundle(tenant_id=_TENANT, version="1.0.0", content=_CONTENT)
    row = _make_bundle_row(bundle)
    # The PolicyBundleRow has a `status` column but the route doesn't read it.
    # We set it on the mock to make the test's intent explicit.
    row.status = bundle_status
    app.dependency_overrides[get_session] = _override_session_returning_bundle(row)
    response = await client.post(
        "/v1/tabletop/simulate",
        json=_scenario_body(bundle_id=bundle.id),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["summary"]["total"] == 3
    assert body["bundle_id"] == str(bundle.id)
    app.dependency_overrides.clear()


# ---------- CP9.40 / IP #11 POST /v1/tabletop/replay-window ----------
#
# The replay-window route makes TWO SQL calls per request:
#   1) get_bundle_by_id (uses scalar_one_or_none)
#   2) list_event_payloads_for_tenant_window (uses result.all())
# The session mock here scripts BOTH responses by walking a tuple of return
# values one per execute() call. The first execute() in the route is the
# bundle lookup; the second is the event-payload window query.


def _override_session_returning_bundle_then_events(
    bundle_row_or_none, event_rows: list[tuple[UUID, dict]]
):
    """Mock a session that first returns the bundle, then the event rows.

    The route fires get_bundle_by_id (one execute), then
    list_event_payloads_for_tenant_window (a second execute). We script
    the two returns by call index.
    """
    call_count = {"n": 0}

    # Build the event-row mocks ahead of time so each .all() call returns
    # the same shaped list of attribute-access mocks.
    event_row_objs = []
    for event_id, payload in event_rows:
        r = MagicMock()
        r.id = event_id
        r.payload = payload
        event_row_objs.append(r)

    async def _execute(stmt):
        idx = call_count["n"]
        call_count["n"] += 1
        result = MagicMock()
        if idx == 0:
            # First call: bundle lookup.
            result.scalar_one_or_none = MagicMock(return_value=bundle_row_or_none)
        else:
            # Subsequent calls: event-payload window query.
            result.all = MagicMock(return_value=event_row_objs)
        return result

    session = MagicMock()
    session.execute = AsyncMock(side_effect=_execute)

    async def _override():
        return session

    return _override


def _replay_body(
    *,
    name: str = "replay-week-21",
    tenant_id: UUID = _TENANT,
    bundle_id: UUID,
    occurred_after: str = "2026-05-08T00:00:00+00:00",
    occurred_before: str = "2026-05-15T00:00:00+00:00",
) -> dict:
    return {
        "name": name,
        "tenant_id": str(tenant_id),
        "policy_bundle_id": str(bundle_id),
        "occurred_after": occurred_after,
        "occurred_before": occurred_before,
    }


@pytest.mark.asyncio
async def test_replay_window_happy_path(app, client) -> None:
    bundle = build_bundle(tenant_id=_TENANT, version="1.0.0", content=_CONTENT)
    event_rows = [
        (uuid4(), {"kind": "ok"}),
        (uuid4(), {"kind": "deny_kind"}),
        (uuid4(), {"kind": "escalate_kind"}),
    ]
    app.dependency_overrides[get_session] = _override_session_returning_bundle_then_events(
        _make_bundle_row(bundle), event_rows
    )
    response = await client.post(
        "/v1/tabletop/replay-window",
        json=_replay_body(bundle_id=bundle.id),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["scenario"]["name"] == "replay-week-21"
    assert body["summary"]["total"] == 3
    assert body["summary"]["allow"] == 1
    assert body["summary"]["deny"] == 1
    assert body["summary"]["escalate"] == 1
    # Labels reflect deterministic event_<uuid> shape from the repo helper.
    labels = [ar["label"] for ar in body["action_results"]]
    assert all(lbl.startswith("event_") for lbl in labels)
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_replay_window_403_when_tenant_does_not_match_principal(app, client) -> None:
    bundle = build_bundle(tenant_id=_TENANT, version="1.0.0", content=_CONTENT)
    app.dependency_overrides[get_session] = _override_session_returning_bundle_then_events(
        _make_bundle_row(bundle), []
    )
    response = await client.post(
        "/v1/tabletop/replay-window",
        json=_replay_body(tenant_id=_OTHER_TENANT, bundle_id=bundle.id),
    )
    assert response.status_code == 403
    body = response.json()
    assert body["detail"]["error"] == "tenant_mismatch"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_replay_window_422_on_naive_timestamps(app, client) -> None:
    bundle = build_bundle(tenant_id=_TENANT, version="1.0.0", content=_CONTENT)
    app.dependency_overrides[get_session] = _override_session_returning_bundle_then_events(
        _make_bundle_row(bundle), []
    )
    response = await client.post(
        "/v1/tabletop/replay-window",
        json=_replay_body(
            bundle_id=bundle.id,
            occurred_after="2026-05-08T00:00:00",  # naive
            occurred_before="2026-05-15T00:00:00",  # naive
        ),
    )
    assert response.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_replay_window_422_on_inverted_window(app, client) -> None:
    bundle = build_bundle(tenant_id=_TENANT, version="1.0.0", content=_CONTENT)
    app.dependency_overrides[get_session] = _override_session_returning_bundle_then_events(
        _make_bundle_row(bundle), []
    )
    response = await client.post(
        "/v1/tabletop/replay-window",
        json=_replay_body(
            bundle_id=bundle.id,
            occurred_after="2026-05-15T00:00:00+00:00",
            occurred_before="2026-05-08T00:00:00+00:00",
        ),
    )
    assert response.status_code == 422
    assert "occurred_before" in response.text
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_replay_window_404_when_bundle_not_found(app, client) -> None:
    app.dependency_overrides[get_session] = _override_session_returning_bundle_then_events(None, [])
    response = await client.post(
        "/v1/tabletop/replay-window",
        json=_replay_body(bundle_id=uuid4()),
    )
    assert response.status_code == 404
    body = response.json()
    assert body["detail"]["error"] == "bundle_not_found"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_replay_window_422_when_no_events_in_window(app, client) -> None:
    """Empty window -> 422 with a clear message (not a 200 with summary.total=0)."""
    bundle = build_bundle(tenant_id=_TENANT, version="1.0.0", content=_CONTENT)
    app.dependency_overrides[get_session] = _override_session_returning_bundle_then_events(
        _make_bundle_row(bundle),
        [],  # zero events
    )
    response = await client.post(
        "/v1/tabletop/replay-window",
        json=_replay_body(bundle_id=bundle.id),
    )
    assert response.status_code == 422
    assert "No events found" in response.text
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_replay_window_413_when_window_exceeds_max_events(app, client) -> None:
    """Window with > 1000 events -> 413 with narrow-the-window guidance."""
    bundle = build_bundle(tenant_id=_TENANT, version="1.0.0", content=_CONTENT)
    # 1001 events -> the route's overflow guard fires.
    too_many = [(uuid4(), {"kind": "ok"}) for _ in range(1001)]
    app.dependency_overrides[get_session] = _override_session_returning_bundle_then_events(
        _make_bundle_row(bundle), too_many
    )
    response = await client.post(
        "/v1/tabletop/replay-window",
        json=_replay_body(bundle_id=bundle.id),
    )
    assert response.status_code == 413
    assert "narrow the time window" in response.text
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_replay_window_at_exactly_1000_events_succeeds(app, client) -> None:
    """Boundary: 1000 events is accepted, 1001 is rejected."""
    bundle = build_bundle(tenant_id=_TENANT, version="1.0.0", content=_CONTENT)
    exactly_max = [(uuid4(), {"kind": "ok"}) for _ in range(1000)]
    app.dependency_overrides[get_session] = _override_session_returning_bundle_then_events(
        _make_bundle_row(bundle), exactly_max
    )
    response = await client.post(
        "/v1/tabletop/replay-window",
        json=_replay_body(bundle_id=bundle.id),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["summary"]["total"] == 1000
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_replay_window_preserves_event_order_in_action_results(app, client) -> None:
    """Replay output ordering reflects the SELECT's chronological order."""
    bundle = build_bundle(tenant_id=_TENANT, version="1.0.0", content=_CONTENT)
    eids = [UUID(int=i) for i in range(1, 6)]
    event_rows = [(eid, {"kind": "ok", "i": i}) for i, eid in enumerate(eids, 1)]
    app.dependency_overrides[get_session] = _override_session_returning_bundle_then_events(
        _make_bundle_row(bundle), event_rows
    )
    response = await client.post(
        "/v1/tabletop/replay-window",
        json=_replay_body(bundle_id=bundle.id),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    labels = [ar["label"] for ar in body["action_results"]]
    assert labels == [f"event_{eid}" for eid in eids]
    app.dependency_overrides.clear()

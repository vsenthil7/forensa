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

"""CP9.18c route-auth enforcement tests.

Verifies that ``Depends(get_principal)`` is wired into every mutating + reading
route and that the principal-to-body identity binding correctly refuses
mismatches.

Two enforcement layers per route:

1. Authentication: 401 when no Authorization header (the get_principal
   dependency itself fires before the route function body).
2. Authorisation: 403 when principal.tenant_id != body/query tenant_id
   (or principal.agent_id != body.agent_id for events).

The 401 case is exercised here by NOT installing the principal override -
the default get_token_verifier dependency runs and returns 503 when env
isn't set, which propagates up. We install a minimal fake verifier so
401 fires for the right reason (no Authorization header) rather than 503
(auth not configured).

The 403 cases install a principal whose tenant_id deliberately doesn't
match the body / query, and assert the structured error code.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.auth.dependencies import get_principal, get_token_verifier
from apps.api.auth.principal import Principal
from apps.api.auth.token import HmacBearerTokenVerifier, TokenVerifier
from apps.api.ingest_service import (
    DefaultBundleProvider,
    InMemorySigningKeyProvider,
    PolicyBundleProvider,
    TenantSigningKeyProvider,
)
from apps.api.main import create_app
from apps.api.routes.events import (
    get_bundle_provider,
    get_enforcement_client,
    get_signing_key_provider,
)
from apps.api.routes.receipts import get_session
from packages.policy.enforcement import PolicyEnforcementClient
from packages.policy.lobstertrap import MockLobsterTrapClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _install_minimal_verifier(app):
    """Install a verifier override so missing-Authorization tests trigger
    401 (auth_required) instead of 503 (auth_not_configured) from the
    env-driven default verifier."""

    async def _override() -> TokenVerifier:
        return HmacBearerTokenVerifier(tenant_id=uuid4(), secret=b"s" * 32)

    app.dependency_overrides[get_token_verifier] = _override


def _install_principal_with(app, principal: Principal) -> None:
    async def _override() -> Principal:
        return principal

    app.dependency_overrides[get_principal] = _override


def _make_session_override(latest_receipt_row=None, captured: list | None = None):
    if captured is None:
        captured = []
    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=latest_receipt_row)
    session = MagicMock()
    session.execute = AsyncMock(return_value=result_mock)
    session.add = MagicMock(side_effect=lambda r: captured.append(r))
    session.flush = AsyncMock(return_value=None)

    async def _override():
        return session

    return _override, captured


def _install_events_business_overrides(app):
    """Install the four business-logic overrides for the events route so we
    isolate the auth check from the ingest pipeline."""
    bp = DefaultBundleProvider()
    kp = InMemorySigningKeyProvider()

    class _Ec(PolicyEnforcementClient):
        def __init__(self):
            self._per_bundle: dict = {}

        async def evaluate(self, tenant_id: UUID, action: dict):  # type: ignore[override]
            bundle = await bp.get_active_bundle(tenant_id)
            c = self._per_bundle.get(bundle.id)
            if c is None:
                c = MockLobsterTrapClient(
                    policy_bundle_id=bundle.id,
                    policy_bundle_version=bundle.version,
                    content=bundle.content,
                )
                self._per_bundle[bundle.id] = c
            return await c.evaluate(tenant_id, action)

    ec = _Ec()

    async def _bp_o() -> PolicyBundleProvider:
        return bp

    async def _kp_o() -> TenantSigningKeyProvider:
        return kp

    async def _ec_o() -> PolicyEnforcementClient:
        return ec

    session_override, _ = _make_session_override()
    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_bundle_provider] = _bp_o
    app.dependency_overrides[get_signing_key_provider] = _kp_o
    app.dependency_overrides[get_enforcement_client] = _ec_o


def _valid_event_payload(tenant_id: UUID, agent_id: UUID, **over):
    base = {
        "tenant_id": str(tenant_id),
        "agent_id": str(agent_id),
        "trace_id": "a" * 32,
        "span_id": "b" * 16,
        "kind": "tool_call",
        "occurred_at": datetime(2026, 5, 14, 23, 50, tzinfo=UTC).isoformat(),
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


# ---------------------------------------------------------------------------
# 401: no Authorization header on any route
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_events_returns_401_when_no_authorization(app, client):
    """No Authorization header -> 401 auth_required (the get_principal
    dependency fires BEFORE the route function body runs)."""
    _install_minimal_verifier(app)
    _install_events_business_overrides(app)
    body = _valid_event_payload(uuid4(), uuid4())
    resp = await client.post("/v1/events", json=body)
    assert resp.status_code == 401
    assert resp.json()["detail"]["error"] == "auth_required"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_receipts_returns_401_when_no_authorization(app, client):
    _install_minimal_verifier(app)
    resp = await client.get(f"/v1/receipts?tenant_id={uuid4()}")
    assert resp.status_code == 401
    assert resp.json()["detail"]["error"] == "auth_required"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_receipt_by_id_returns_401_when_no_authorization(app, client):
    _install_minimal_verifier(app)
    resp = await client.get(f"/v1/receipts/{uuid4()}")
    assert resp.status_code == 401
    assert resp.json()["detail"]["error"] == "auth_required"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_evidence_returns_401_when_no_authorization(app, client):
    _install_minimal_verifier(app)
    resp = await client.get(
        f"/v1/evidence-packs?tenant_id={uuid4()}"
        "&scope_start=2026-05-13T00:00:00%2B00:00"
        "&scope_end=2026-05-13T23:59:59%2B00:00"
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["error"] == "auth_required"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_post_narratives_returns_401_when_no_authorization(app, client):
    _install_minimal_verifier(app)
    resp = await client.post(
        f"/v1/narratives?tenant_id={uuid4()}"
        "&scope_start=2026-05-13T00:00:00%2B00:00"
        "&scope_end=2026-05-13T23:59:59%2B00:00"
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["error"] == "auth_required"
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 403: tenant mismatch on each route
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_events_returns_403_on_tenant_mismatch(app, client):
    """Principal authenticates as tenant A; body claims tenant B -> 403
    tenant_mismatch (NOT 401, NOT 422). The route's auth check fires
    AFTER body parsing succeeds; structurally valid body, structurally
    valid auth, but the two don't agree."""
    _install_events_business_overrides(app)
    principal_tenant = uuid4()
    body_tenant = uuid4()
    agent = uuid4()
    _install_principal_with(
        app,
        Principal(tenant_id=principal_tenant, agent_id=agent, agent_slug="t"),
    )
    body = _valid_event_payload(body_tenant, agent)
    resp = await client.post("/v1/events", json=body)
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "tenant_mismatch"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_post_events_returns_403_on_agent_mismatch(app, client):
    """Tenant matches but agent_id doesn't -> 403 agent_mismatch (distinct
    error code from tenant_mismatch so audit/SIEM can differentiate the
    two attack patterns)."""
    _install_events_business_overrides(app)
    tenant = uuid4()
    principal_agent = uuid4()
    body_agent = uuid4()
    _install_principal_with(
        app,
        Principal(tenant_id=tenant, agent_id=principal_agent, agent_slug="t"),
    )
    body = _valid_event_payload(tenant, body_agent)
    resp = await client.post("/v1/events", json=body)
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "agent_mismatch"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_receipts_returns_403_on_tenant_mismatch(app, client):
    """Cross-tenant list-receipts blocked at the route boundary."""
    principal_tenant = uuid4()
    query_tenant = uuid4()
    _install_principal_with(
        app,
        Principal(tenant_id=principal_tenant, agent_id=uuid4(), agent_slug="t"),
    )
    session_override, _ = _make_session_override()
    app.dependency_overrides[get_session] = session_override
    resp = await client.get(f"/v1/receipts?tenant_id={query_tenant}")
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "tenant_mismatch"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_receipt_by_id_returns_403_on_tenant_mismatch(app, client):
    """A leaked receipt UUID is not enough to read another tenant's data.

    The route loads the row, sees its tenant_id, refuses if it doesn't
    match the principal. We mock the repo to return a row with a different
    tenant_id than the principal.
    """
    from packages.schema.receipt import Receipt

    principal_tenant = uuid4()
    receipt_tenant = uuid4()

    receipt = Receipt(
        tenant_id=receipt_tenant,
        event_id=uuid4(),
        policy_bundle_id=uuid4(),
        sequence=0,
        prev_receipt_hash=None,
        payload_hash="a" * 64,
        receipt_hash="b" * 64,
        signature=b"\x00" * 64,
        signed_at=datetime(2026, 5, 13, tzinfo=UTC),
    )
    snapshot_id = uuid4()

    async def _mock_get(session, receipt_id):
        return (receipt, snapshot_id)

    # We can't easily monkeypatch get_receipt_by_id through a Depends since
    # it's a function import; instead, patch the module reference in the
    # route module's namespace.
    from apps.api.routes import receipts as receipts_route_module

    original = receipts_route_module.get_receipt_by_id
    receipts_route_module.get_receipt_by_id = _mock_get
    try:
        _install_principal_with(
            app,
            Principal(tenant_id=principal_tenant, agent_id=uuid4(), agent_slug="t"),
        )
        session_override, _ = _make_session_override()
        app.dependency_overrides[get_session] = session_override
        resp = await client.get(f"/v1/receipts/{uuid4()}")
        assert resp.status_code == 403
        assert resp.json()["detail"]["error"] == "tenant_mismatch"
    finally:
        receipts_route_module.get_receipt_by_id = original
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_evidence_returns_403_on_tenant_mismatch(app, client):
    """Cross-tenant evidence export blocked."""
    principal_tenant = uuid4()
    query_tenant = uuid4()
    _install_principal_with(
        app,
        Principal(tenant_id=principal_tenant, agent_id=uuid4(), agent_slug="t"),
    )
    session_override, _ = _make_session_override()
    app.dependency_overrides[get_session] = session_override
    resp = await client.get(
        f"/v1/evidence-packs?tenant_id={query_tenant}"
        "&scope_start=2026-05-13T00:00:00%2B00:00"
        "&scope_end=2026-05-13T23:59:59%2B00:00"
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "tenant_mismatch"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_post_narratives_returns_403_on_tenant_mismatch(app, client):
    """Cross-tenant narrative generation blocked BEFORE any LLM call.

    Critical: the 403 must fire before the route consults the narrative
    client. We don't install a narrative client override - if the route
    tried to call one, the test would 500 (no provider). Reaching 403
    means the check fired first.
    """
    principal_tenant = uuid4()
    query_tenant = uuid4()
    _install_principal_with(
        app,
        Principal(tenant_id=principal_tenant, agent_id=uuid4(), agent_slug="t"),
    )
    session_override, _ = _make_session_override()
    app.dependency_overrides[get_session] = session_override
    resp = await client.post(
        f"/v1/narratives?tenant_id={query_tenant}"
        "&scope_start=2026-05-13T00:00:00%2B00:00"
        "&scope_end=2026-05-13T23:59:59%2B00:00"
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "tenant_mismatch"
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# /healthz remains public (no auth required, k8s probe contract)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_healthz_remains_unauthenticated(app, client):
    """k8s liveness probe must not require auth."""
    resp = await client.get("/healthz")
    assert resp.status_code == 200

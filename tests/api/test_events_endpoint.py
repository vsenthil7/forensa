"""Tests for POST /v1/events ingest endpoint (CP9.11 full persistence).

CP9.11 changed the route from a 202-noop into a 201-persisted endpoint that
runs the full ingest pipeline (resolve bundle, evaluate policy, build +
sign Receipt, atomically persist snapshot/event/receipt, live-verify
integrity). These tests:

1. Validate the new 201 response shape and the new fields
   (``receipt_id``, ``policy_snapshot_id``, ``receipt_hash``,
   ``integrity_ok``).
2. Confirm schema validation still gives 422 with the same matrix of bad
   inputs (trace_id, span_id, kind, occurred_at tz, missing required,
   extra field).
3. Confirm idempotency-of-shape across all EventKind values.
4. Confirm headers ``X-Forensa-Event-Id`` + ``X-Forensa-Receipt-Id`` are set.
5. Use ``app.dependency_overrides`` to swap in test providers that don't
   need Postgres - identical pattern to ``tests/api/test_receipts_route.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

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
from tests.api._auth_helpers import install_principal_override

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_event_payload(tenant_id: UUID | None = None, agent_id: UUID | None = None, **over):
    """Return a fresh valid POST /v1/events body. Override any field via kwargs.

    CP9.18c: when ``tenant_id`` / ``agent_id`` are supplied, they're used
    directly; otherwise a fresh UUID is generated. Tests pairing this with
    ``_install_overrides`` should pass the same ids so the body matches the
    installed Principal.
    """
    base = {
        "tenant_id": str(tenant_id if tenant_id is not None else uuid4()),
        "agent_id": str(agent_id if agent_id is not None else uuid4()),
        "trace_id": "a" * 32,
        "span_id": "b" * 16,
        "kind": "tool_call",
        "occurred_at": datetime(2026, 5, 13, 9, 50, tzinfo=UTC).isoformat(),
    }
    base.update(over)
    return base


def _make_session_override(
    *,
    latest_receipt_row=None,
    captured_rows: list | None = None,
):
    """Build a get_session override that mocks the AsyncSession interface.

    The ingest path calls:
      1. ``get_latest_receipt_for_tenant(session, tenant_id)`` -> session.execute()
         -> result.scalar_one_or_none() -> ReceiptRow OR None
      2. ``session.add(snapshot_row)``
      3. ``session.add(event_row)``
      4. ``session.add(receipt_row)``
      5. ``await session.flush()``

    ``captured_rows`` (if provided) collects every row passed to session.add()
    so tests can inspect what was persisted.
    """
    if captured_rows is None:
        captured_rows = []

    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=latest_receipt_row)

    session = MagicMock()
    session.execute = AsyncMock(return_value=result_mock)
    session.add = MagicMock(side_effect=lambda row: captured_rows.append(row))
    session.flush = AsyncMock(return_value=None)

    async def _override():
        return session

    return _override, captured_rows


class _TestPolicyEnforcement(PolicyEnforcementClient):
    """Wraps a MockLobsterTrapClient bound to the same bundle the test bundle
    provider returns, so verdicts bind the right policy_bundle_id."""

    def __init__(self, bundle_provider: PolicyBundleProvider) -> None:
        self._bundle_provider = bundle_provider
        self._per_bundle: dict = {}

    async def evaluate(self, tenant_id: UUID, action: dict):  # type: ignore[override]
        bundle = await self._bundle_provider.get_active_bundle(tenant_id)
        client = self._per_bundle.get(bundle.id)
        if client is None:
            client = MockLobsterTrapClient(
                policy_bundle_id=bundle.id,
                policy_bundle_version=bundle.version,
                content=bundle.content,
            )
            self._per_bundle[bundle.id] = client
        return await client.evaluate(tenant_id, action)


def _install_overrides(
    app,
    *,
    latest_receipt_row=None,
    captured_rows: list | None = None,
    tenant_id: UUID | None = None,
    agent_id: UUID | None = None,
):
    """Install a coherent set of overrides for one test. Returns
    ``(captured_rows, tenant_id, agent_id)`` so callers can pass those into
    ``_valid_event_payload`` to keep the principal/body identity aligned
    (CP9.18c). ``tenant_id`` / ``agent_id`` default to freshly generated
    UUIDs.

    The installed Principal matches the returned (tenant_id, agent_id) so
    the route's identity-binding check passes. Negative tests that WANT a
    tenant_mismatch can explicitly override the Principal afterwards.
    """
    bundle_provider = DefaultBundleProvider()
    signing_key_provider = InMemorySigningKeyProvider()
    enforcement_client = _TestPolicyEnforcement(bundle_provider)

    session_override, captured = _make_session_override(
        latest_receipt_row=latest_receipt_row,
        captured_rows=captured_rows,
    )

    async def _bp_override() -> PolicyBundleProvider:
        return bundle_provider

    async def _kp_override() -> TenantSigningKeyProvider:
        return signing_key_provider

    async def _ec_override() -> PolicyEnforcementClient:
        return enforcement_client

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_bundle_provider] = _bp_override
    app.dependency_overrides[get_signing_key_provider] = _kp_override
    app.dependency_overrides[get_enforcement_client] = _ec_override

    # CP9.18c: install a Principal matching the returned (tenant_id, agent_id)
    # so the route's identity-binding check passes.
    resolved_tenant = tenant_id if tenant_id is not None else uuid4()
    resolved_agent = agent_id if agent_id is not None else uuid4()
    install_principal_override(app, tenant_id=resolved_tenant, agent_id=resolved_agent)

    return captured, resolved_tenant, resolved_agent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Happy path - 201 with full persistence + integrity check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_event_persists_and_returns_201(app, client):
    captured, tid, aid = _install_overrides(app)
    resp = await client.post("/v1/events", json=_valid_event_payload(tenant_id=tid, agent_id=aid))
    assert resp.status_code == 201
    body = resp.json()
    # New CP9.11 shape
    assert "event_id" in body
    assert "receipt_id" in body
    assert "policy_snapshot_id" in body
    assert "receipt_hash" in body
    assert body["status"] == "created"
    assert "persisted_at" in body
    # Integrity must be OK on a fresh write
    assert body["integrity_ok"] is True
    # Receipt hash is a 64-char hex
    assert len(body["receipt_hash"]) == 64
    int(body["receipt_hash"], 16)  # raises if non-hex
    # Persistence happened: 3 rows added (snapshot, event, receipt)
    assert len(captured) == 3
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_post_event_returns_response_headers(app, client):
    _, tid, aid = _install_overrides(app)
    resp = await client.post("/v1/events", json=_valid_event_payload(tenant_id=tid, agent_id=aid))
    assert resp.status_code == 201
    body = resp.json()
    assert resp.headers["X-Forensa-Event-Id"] == body["event_id"]
    assert resp.headers["X-Forensa-Receipt-Id"] == body["receipt_id"]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_post_event_accepts_full_payload(app, client):
    _, tid, aid = _install_overrides(app)
    payload = _valid_event_payload(
        tenant_id=tid,
        agent_id=aid,
        parent_span_id="c" * 16,
        payload={"tool": "search", "args": {"q": "foo"}},
        reasoning="User asked X so I called search.",
        output="The top results are ...",
        policy_version="1.4.2",
        policy_verdict="allow",
    )
    resp = await client.post("/v1/events", json=payload)
    assert resp.status_code == 201
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_post_event_persisted_at_is_recent(app, client):
    _, tid, aid = _install_overrides(app)
    before = datetime.now(UTC)
    resp = await client.post("/v1/events", json=_valid_event_payload(tenant_id=tid, agent_id=aid))
    after = datetime.now(UTC)
    persisted_at = datetime.fromisoformat(resp.json()["persisted_at"])
    assert before <= persisted_at <= after
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_post_event_returns_unique_event_and_receipt_ids(app, client):
    _, tid1, aid1 = _install_overrides(app)
    r1 = await client.post("/v1/events", json=_valid_event_payload(tenant_id=tid1, agent_id=aid1))
    _, tid2, aid2 = _install_overrides(app)  # reset captured rows + fresh principal
    r2 = await client.post("/v1/events", json=_valid_event_payload(tenant_id=tid2, agent_id=aid2))
    assert r1.json()["event_id"] != r2.json()["event_id"]
    assert r1.json()["receipt_id"] != r2.json()["receipt_id"]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_post_event_with_all_event_kinds(app, client):
    for kind in [
        "tool_call",
        "tool_result",
        "llm_invocation",
        "auth_decision",
        "policy_verdict",
        "agent_message",
        "resource_access",
    ]:
        _, tid, aid = _install_overrides(app)
        resp = await client.post(
            "/v1/events",
            json=_valid_event_payload(tenant_id=tid, agent_id=aid, kind=kind),
        )
        assert resp.status_code == 201, f"kind={kind} should be accepted (got {resp.status_code})"
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Chain linkage - genesis vs non-genesis prev_receipt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_genesis_event_has_no_prev_receipt_hash(app, client):
    """First event for a tenant -> Receipt.prev_receipt_hash is None,
    sequence == 0. We check this by inspecting the captured ReceiptRow."""
    captured, tid, aid = _install_overrides(app)
    resp = await client.post("/v1/events", json=_valid_event_payload(tenant_id=tid, agent_id=aid))
    assert resp.status_code == 201
    receipt_row = captured[2]  # 3rd row added (snapshot, event, receipt)
    assert receipt_row.sequence == 0
    assert receipt_row.prev_receipt_hash is None
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_second_event_links_to_previous_receipt(app, client):
    """When a previous Receipt exists for the tenant, the new Receipt's
    sequence is prev.sequence + 1 and prev_receipt_hash = prev.receipt_hash."""
    from packages.ledger.models import ReceiptRow

    # Build a fake "latest" Receipt row to return from session.execute
    fake_prev = MagicMock(spec=ReceiptRow)
    fake_prev.id = uuid4()
    fake_prev.tenant_id = uuid4()
    fake_prev.event_id = uuid4()
    fake_prev.policy_bundle_id = uuid4()
    fake_prev.sequence = 42
    fake_prev.prev_receipt_hash = "f" * 64
    fake_prev.payload_hash = "1" * 64
    fake_prev.receipt_hash = "deadbeef" * 8  # 64 chars
    fake_prev.signature = b"\x00" * 64
    fake_prev.agent_signature = None  # CP9.18: pre-migration-0006 chain head
    fake_prev.signed_at = datetime(2026, 5, 13, tzinfo=UTC)

    aid = uuid4()
    # CP9.18c: install the principal whose tenant matches fake_prev.tenant_id
    # so the body's tenant_id (=fake_prev.tenant_id) passes the identity check.
    captured, _, _ = _install_overrides(
        app,
        latest_receipt_row=fake_prev,
        tenant_id=fake_prev.tenant_id,
        agent_id=aid,
    )
    payload = _valid_event_payload(tenant_id=fake_prev.tenant_id, agent_id=aid)
    resp = await client.post("/v1/events", json=payload)
    assert resp.status_code == 201
    receipt_row = captured[2]
    assert receipt_row.sequence == 43
    assert receipt_row.prev_receipt_hash == fake_prev.receipt_hash
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Schema validation (still 422 - FastAPI's default for Pydantic failures)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_event_rejects_bad_trace_id(app, client):
    _install_overrides(app)
    bad = _valid_event_payload(trace_id="too-short")
    resp = await client.post("/v1/events", json=bad)
    assert resp.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_post_event_rejects_bad_span_id(app, client):
    _install_overrides(app)
    bad = _valid_event_payload(span_id="BAD")
    resp = await client.post("/v1/events", json=bad)
    assert resp.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_post_event_rejects_invalid_kind(app, client):
    _install_overrides(app)
    bad = _valid_event_payload(kind="not_a_valid_kind")
    resp = await client.post("/v1/events", json=bad)
    assert resp.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_post_event_rejects_naive_timestamp(app, client):
    _install_overrides(app)
    bad = _valid_event_payload(occurred_at="2026-05-13T09:50:00")
    resp = await client.post("/v1/events", json=bad)
    assert resp.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_post_event_rejects_missing_required_field(app, client):
    _install_overrides(app)
    payload = _valid_event_payload()
    del payload["trace_id"]
    resp = await client.post("/v1/events", json=payload)
    assert resp.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_post_event_rejects_extra_field(app, client):
    _install_overrides(app)
    payload = _valid_event_payload(evil="data")
    resp = await client.post("/v1/events", json=payload)
    assert resp.status_code == 422
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Ingest service errors map to 422 with structured body
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_event_maps_ingest_failure_to_422(app, client, monkeypatch):
    """If the enforcement client raises, the route returns 422 with a
    structured error body so callers can distinguish from schema failures."""
    _, tid, aid = _install_overrides(app)

    # Patch ingest_event to raise IngestServiceError
    from apps.api.ingest_service import IngestServiceError
    from apps.api.routes import events as events_module

    async def _boom(**kwargs):
        raise IngestServiceError("policy enforcement failed: simulated outage")

    monkeypatch.setattr(events_module, "ingest_event", _boom)

    resp = await client.post("/v1/events", json=_valid_event_payload(tenant_id=tid, agent_id=aid))
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["error"] == "ingest_failed"
    assert "simulated outage" in detail["reason"]
    app.dependency_overrides.clear()

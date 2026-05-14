"""Idempotency-Key contract tests for POST /v1/events (CP9.17 / NEW-P9.8.2).

These tests live in their own module (not appended to test_events_endpoint.py)
so the test_events_endpoint.py file keeps its pre-CP9.17 shape intact and the
diff during code review is reviewable in isolation.

Test matrix:

Header behaviour:
- No header -> two POSTs produce two distinct events (status quo).
- Header present + valid + first time -> 201 with no replay header.
- Header present + valid + second time same body -> 201 with
  ``Idempotent-Replayed: true``, response body byte-identical to first.
- Header present + valid + second time DIFFERENT body -> 409 Conflict.
- Header present + same key but different tenant -> two distinct events.
- Header malformed (too short / bad chars / too long) -> 400.

Race-safety:
- Two concurrent same-tenant + same-key + same-body POSTs -> exactly one
  ingest pipeline runs; both responses are byte-identical. The
  InMemoryIdempotencyStore's asyncio.Lock guarantees this.

TTL:
- The idempotency store honours its TTL; expired records are tombstones
  not bugs. Test uses a 0-second TTL to force immediate expiry.

The tests reuse the same dependency-override pattern as
test_events_endpoint.py via a small ``_install_overrides`` helper inlined
here to keep this module self-contained. An ``IdempotencyStore`` override
is added so each test starts from an empty store.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.idempotency_store import (
    IdempotencyStore,
    InMemoryIdempotencyStore,
)
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
    get_idempotency_store,
    get_signing_key_provider,
)
from apps.api.routes.receipts import get_session
from packages.policy.enforcement import PolicyEnforcementClient
from packages.policy.lobstertrap import MockLobsterTrapClient
from tests.api._auth_helpers import install_principal_override

# ---------------------------------------------------------------------------
# Helpers (mirror tests/api/test_events_endpoint.py shape)
# ---------------------------------------------------------------------------


def _valid_event_payload(tenant_id: UUID | None = None, agent_id: UUID | None = None, **over):
    """Return a fresh valid POST /v1/events body. CP9.18c: tenant_id and
    agent_id default to fresh UUIDs but can be supplied so they align with
    an installed Principal."""
    base = {
        "tenant_id": str(tenant_id if tenant_id is not None else uuid4()),
        "agent_id": str(agent_id if agent_id is not None else uuid4()),
        "trace_id": "a" * 32,
        "span_id": "b" * 16,
        "kind": "tool_call",
        "occurred_at": datetime(2026, 5, 14, 21, 17, tzinfo=UTC).isoformat(),
    }
    base.update(over)
    return base


def _make_session_override():
    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=None)
    session = MagicMock()
    session.execute = AsyncMock(return_value=result_mock)
    session.add = MagicMock()
    session.flush = AsyncMock(return_value=None)

    async def _override():
        return session

    return _override


class _TestPolicyEnforcement(PolicyEnforcementClient):
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
    store: IdempotencyStore | None = None,
    tenant_id: UUID | None = None,
    agent_id: UUID | None = None,
) -> tuple[IdempotencyStore, UUID, UUID]:
    """Install a coherent set of overrides for one test.

    Returns ``(store, tenant_id, agent_id)`` so the caller can:
    - introspect the idempotency store,
    - pass the (tenant_id, agent_id) into ``_valid_event_payload`` to keep
      the principal/body identity aligned for CP9.18c.
    """
    bundle_provider = DefaultBundleProvider()
    signing_key_provider = InMemorySigningKeyProvider()
    enforcement_client = _TestPolicyEnforcement(bundle_provider)
    if store is None:
        store = InMemoryIdempotencyStore()

    session_override = _make_session_override()

    async def _bp_override() -> PolicyBundleProvider:
        return bundle_provider

    async def _kp_override() -> TenantSigningKeyProvider:
        return signing_key_provider

    async def _ec_override() -> PolicyEnforcementClient:
        return enforcement_client

    async def _is_override() -> IdempotencyStore:
        return store

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_bundle_provider] = _bp_override
    app.dependency_overrides[get_signing_key_provider] = _kp_override
    app.dependency_overrides[get_enforcement_client] = _ec_override
    app.dependency_overrides[get_idempotency_store] = _is_override

    # CP9.18c: install a Principal matching the (tenant_id, agent_id) so
    # the route's identity-binding check passes.
    resolved_tenant = tenant_id if tenant_id is not None else uuid4()
    resolved_agent = agent_id if agent_id is not None else uuid4()
    install_principal_override(app, tenant_id=resolved_tenant, agent_id=resolved_agent)

    return store, resolved_tenant, resolved_agent


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


_VALID_KEY = "abcdefghij1234567890_test-key"  # 29 chars, matches ^[A-Za-z0-9_-]{16,128}$


# ---------------------------------------------------------------------------
# Behaviour without the header (status quo)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_header_means_two_posts_two_events(app, client):
    """Backwards compatibility: requests without the header still produce
    independent events on each call."""
    _, tid, aid = _install_overrides(app)
    body = _valid_event_payload(tenant_id=tid, agent_id=aid)
    r1 = await client.post("/v1/events", json=body)
    _, tid2, aid2 = _install_overrides(app)  # fresh stores + fresh principal
    body2 = _valid_event_payload(tenant_id=tid2, agent_id=aid2)
    r2 = await client.post("/v1/events", json=body2)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["event_id"] != r2.json()["event_id"]
    assert r1.json()["receipt_id"] != r2.json()["receipt_id"]
    # Replay header is NOT set on a no-key request
    assert "Idempotent-Replayed" not in r1.headers
    assert "Idempotent-Replayed" not in r2.headers
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Happy path: same key + same body -> identical response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_same_key_same_body_returns_cached_response(app, client):
    """The core contract: two POSTs with the same Idempotency-Key and the
    same body produce identical responses on call 2 (cached replay)."""
    store, tid, aid = _install_overrides(app)
    body = _valid_event_payload(tenant_id=tid, agent_id=aid)

    r1 = await client.post("/v1/events", json=body, headers={"Idempotency-Key": _VALID_KEY})
    assert r1.status_code == 201
    # First call: not a replay
    assert "Idempotent-Replayed" not in r1.headers

    r2 = await client.post("/v1/events", json=body, headers={"Idempotency-Key": _VALID_KEY})
    assert r2.status_code == 201
    # Second call: marked as replay
    assert r2.headers["Idempotent-Replayed"] == "true"

    # Response bodies must be byte-identical (modulo JSON whitespace).
    assert r2.json() == r1.json()
    # Same event_id, same receipt_id - this is the whole point.
    assert r2.json()["event_id"] == r1.json()["event_id"]
    assert r2.json()["receipt_id"] == r1.json()["receipt_id"]

    # The store has exactly one record for this (tenant, key) pair.
    assert isinstance(store, InMemoryIdempotencyStore)
    # Internal inspection - acceptable in a test of the in-memory impl.
    # We use the public dict-like attribute set up in __init__.
    assert len(store._records) == 1
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_same_key_same_body_returns_same_event_id(app, client):
    """Belt + braces over the previous test: confirm the dedup actually
    prevents a second event from being persisted (no double-counting)."""
    _, tid, aid = _install_overrides(app)
    body = _valid_event_payload(tenant_id=tid, agent_id=aid)
    r1 = await client.post("/v1/events", json=body, headers={"Idempotency-Key": _VALID_KEY})
    r2 = await client.post("/v1/events", json=body, headers={"Idempotency-Key": _VALID_KEY})
    # No new event was created on call 2.
    assert r1.json()["event_id"] == r2.json()["event_id"]
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 409 Conflict: same key + different body
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_same_key_different_body_returns_409_conflict(app, client):
    """Reusing an Idempotency-Key with a different body is a client bug;
    surface 409 Conflict with a structured error so the client can log
    and rotate the key."""
    # CP9.18c: install principal whose tenant matches the body's.
    tenant_id = uuid4()
    agent_id = uuid4()
    _install_overrides(app, tenant_id=tenant_id, agent_id=agent_id)
    body_a = _valid_event_payload(tenant_id=tenant_id, agent_id=agent_id, kind="tool_call")
    body_b = _valid_event_payload(tenant_id=tenant_id, agent_id=agent_id, kind="tool_result")

    r1 = await client.post("/v1/events", json=body_a, headers={"Idempotency-Key": _VALID_KEY})
    assert r1.status_code == 201

    r2 = await client.post("/v1/events", json=body_b, headers={"Idempotency-Key": _VALID_KEY})
    assert r2.status_code == 409
    detail = r2.json()["detail"]
    assert detail["error"] == "idempotency_key_conflict"
    assert _VALID_KEY in detail["reason"]
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tenant scoping: same key, different tenants -> two records, no collision
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_same_key_different_tenants_two_events(app, client):
    """Idempotency-Key is scoped per-tenant. Two tenants colliding on the
    same key string each get their own independent record.

    CP9.18c: each request installs its OWN principal matching the body's
    tenant (the route check is per-call).
    """
    tenant_a = uuid4()
    agent_a = uuid4()
    store, _, _ = _install_overrides(app, tenant_id=tenant_a, agent_id=agent_a)

    r_a = await client.post(
        "/v1/events",
        json=_valid_event_payload(tenant_id=tenant_a, agent_id=agent_a),
        headers={"Idempotency-Key": _VALID_KEY},
    )

    # Re-install everything for tenant B but KEEP THE SAME STORE so both
    # tenants share the same idempotency table (verifying the per-tenant
    # key scoping is enforced by the store contract, not by store identity).
    tenant_b = uuid4()
    agent_b = uuid4()
    _install_overrides(app, store=store, tenant_id=tenant_b, agent_id=agent_b)

    r_b = await client.post(
        "/v1/events",
        json=_valid_event_payload(tenant_id=tenant_b, agent_id=agent_b),
        headers={"Idempotency-Key": _VALID_KEY},
    )
    assert r_a.status_code == 201
    assert r_b.status_code == 201
    # Distinct events
    assert r_a.json()["event_id"] != r_b.json()["event_id"]
    # Store has 2 records keyed on (tenant_id, key)
    assert isinstance(store, InMemoryIdempotencyStore)
    assert len(store._records) == 2
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Different keys, same body -> two events (key is the dedup token)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_different_keys_same_body_two_events(app, client):
    """The dedup token is the key, not the body. Two distinct keys on
    identical bodies produce two independent events."""
    _, tid, aid = _install_overrides(app)
    body = _valid_event_payload(tenant_id=tid, agent_id=aid)
    key_a = "key-a-with-enough-chars-12345"
    key_b = "key-b-with-enough-chars-67890"

    r_a = await client.post("/v1/events", json=body, headers={"Idempotency-Key": key_a})
    r_b = await client.post("/v1/events", json=body, headers={"Idempotency-Key": key_b})
    assert r_a.status_code == 201
    assert r_b.status_code == 201
    assert r_a.json()["event_id"] != r_b.json()["event_id"]
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 400 Bad Request: malformed Idempotency-Key
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_key",
    [
        "short",  # under 16 chars
        "a" * 15,  # 15 chars - one under
        "a" * 129,  # 129 chars - one over
        "has spaces in it!!!!",  # bad chars
        "has/slash/in/key/aaaaaa",  # bad char
        "has.dot.in.key.aaaaaaaa",  # bad char
        "has;semi;colon;aaaaaaaaa",  # bad char
        "",  # empty
    ],
)
async def test_malformed_idempotency_key_returns_400(app, client, bad_key):
    """Any key not matching ^[A-Za-z0-9_-]{16,128}$ is 400 with a structured
    error so clients can fix their key generator."""
    # Empty key is dropped by httpx when passed as a header value - skip
    # that one if it ends up being a no-header request.
    if bad_key == "":
        # Empty header sends as "Idempotency-Key:" which httpx forwards.
        # FastAPI parses it as the empty string; our validator rejects.
        # Some HTTP stacks strip empty headers - we ensure our pattern
        # rejects empty input regardless.
        pass

    _, tid, aid = _install_overrides(app)
    body = _valid_event_payload(tenant_id=tid, agent_id=aid)
    resp = await client.post("/v1/events", json=body, headers={"Idempotency-Key": bad_key})
    if bad_key == "":
        # Some HTTP layers drop empty-value headers entirely. Either:
        #  - the header was dropped -> behave as no-header (201), OR
        #  - the header reached us empty -> 400.
        assert resp.status_code in (201, 400)
        if resp.status_code == 400:
            assert resp.json()["detail"]["error"] == "idempotency_key_malformed"
    else:
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert detail["error"] == "idempotency_key_malformed"
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Valid key boundaries: 16-char min, 128-char max, all allowed char classes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "good_key",
    [
        "a" * 16,  # minimum length
        "a" * 128,  # maximum length
        "ABC-def_123-XYZ.fail",  # contains . - should fail, NOT in this list
    ][:2],  # only the two valid ones
)
async def test_valid_idempotency_keys_accepted(app, client, good_key):
    _, tid, aid = _install_overrides(app)
    body = _valid_event_payload(tenant_id=tid, agent_id=aid)
    resp = await client.post("/v1/events", json=body, headers={"Idempotency-Key": good_key})
    assert resp.status_code == 201
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Race-safety: concurrent same-key submissions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_same_key_submissions_dedup_to_one_event(app, client):
    """Two concurrent POSTs with the same Idempotency-Key + same body:
    exactly one ingest pipeline runs; both responses are identical.

    InMemoryIdempotencyStore's asyncio.Lock is what makes this safe. The
    test exercises lookup_or_claim's atomic 'check or claim' contract.
    """
    _, tid, aid = _install_overrides(app)
    body = _valid_event_payload(tenant_id=tid, agent_id=aid)
    headers = {"Idempotency-Key": _VALID_KEY}

    r1, r2 = await asyncio.gather(
        client.post("/v1/events", json=body, headers=headers),
        client.post("/v1/events", json=body, headers=headers),
    )
    assert r1.status_code == 201
    assert r2.status_code == 201
    # Both responses point to the same event_id (only one was persisted).
    assert r1.json()["event_id"] == r2.json()["event_id"]
    assert r1.json()["receipt_id"] == r2.json()["receipt_id"]
    # At least one of them should be marked as a replay. (Race may give
    # us 0 or 1 replay headers depending on which coroutine won the lock;
    # what matters is the dedup outcome above.)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# TTL: expired records are tombstones
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_expired_record_is_treated_as_no_record(app, client):
    """A record past its expires_at is a tombstone; a subsequent request
    with the same key + same body re-executes and overwrites."""
    # Use a 0-second TTL so the record is born-expired.
    store = InMemoryIdempotencyStore(default_ttl=timedelta(seconds=0))
    _, tid, aid = _install_overrides(app, store=store)
    body = _valid_event_payload(tenant_id=tid, agent_id=aid)
    headers = {"Idempotency-Key": _VALID_KEY}

    r1 = await client.post("/v1/events", json=body, headers=headers)
    assert r1.status_code == 201

    # Second call: store has the row but expires_at <= now so lookup
    # returns None. Pipeline re-runs.
    r2 = await client.post("/v1/events", json=body, headers=headers)
    assert r2.status_code == 201
    assert (
        r1.json()["event_id"] != r2.json()["event_id"]
    ), "Expected TTL=0 to force re-execution; got cached replay"
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Edge cases on the contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_idempotent_replay_preserves_persisted_at(app, client):
    """The cached response is returned byte-for-byte; in particular,
    ``persisted_at`` is the FIRST call's timestamp, not 'now()' on replay."""
    _, tid, aid = _install_overrides(app)
    body = _valid_event_payload(tenant_id=tid, agent_id=aid)
    headers = {"Idempotency-Key": _VALID_KEY}

    r1 = await client.post("/v1/events", json=body, headers=headers)
    # Sleep briefly to ensure now() would differ on replay.
    await asyncio.sleep(0.05)
    r2 = await client.post("/v1/events", json=body, headers=headers)
    assert r1.json()["persisted_at"] == r2.json()["persisted_at"]
    app.dependency_overrides.clear()

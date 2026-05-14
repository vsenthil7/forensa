"""Unit tests for apps.api.ingest_service (CP9.11)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from apps.api.ingest_service import (
    DefaultBundleProvider,
    IngestServiceError,
    InMemorySigningKeyProvider,
    ingest_event,
)
from packages.policy.bundle_builder import build_bundle
from packages.policy.enforcement import PolicyEnforcementClient
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.schema.event import Event, EventKind


def _event(tenant_id: UUID | None = None) -> Event:
    return Event(
        tenant_id=tenant_id or uuid4(),
        agent_id=uuid4(),
        trace_id="a" * 32,
        span_id="b" * 16,
        kind=EventKind.TOOL_CALL,
        occurred_at=__import__("datetime").datetime(2026, 5, 13, tzinfo=__import__("datetime").UTC),
    )


def _mock_session(latest_receipt_row=None) -> MagicMock:
    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=latest_receipt_row)
    session = MagicMock()
    session.execute = AsyncMock(return_value=result_mock)
    session.add = MagicMock()
    session.flush = AsyncMock(return_value=None)
    return session


# ---------------------------------------------------------------------------
# DefaultBundleProvider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_default_bundle_provider_returns_bundle_for_tenant():
    p = DefaultBundleProvider()
    tid = uuid4()
    bundle = await p.get_active_bundle(tid)
    assert bundle.tenant_id == tid
    assert bundle.version == "1.0.0"


@pytest.mark.asyncio
async def test_default_bundle_provider_caches_per_tenant():
    """Second call for the same tenant returns the identical PolicyBundle
    (covering line 139 - the cache-hit branch)."""
    p = DefaultBundleProvider()
    tid = uuid4()
    b1 = await p.get_active_bundle(tid)
    b2 = await p.get_active_bundle(tid)
    assert b1 is b2  # cache hit returns same instance


# ---------------------------------------------------------------------------
# InMemorySigningKeyProvider
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_signing_key_provider_returns_32_byte_key():
    p = InMemorySigningKeyProvider()
    tid = uuid4()
    key = await p.get_signing_key(tid)
    assert isinstance(key, bytes)
    assert len(key) == 32


@pytest.mark.asyncio
async def test_signing_key_provider_caches_per_tenant():
    """Same tenant -> same key bytes (cache hit branch)."""
    p = InMemorySigningKeyProvider()
    tid = uuid4()
    k1 = await p.get_signing_key(tid)
    k2 = await p.get_signing_key(tid)
    assert k1 == k2


# ---------------------------------------------------------------------------
# ingest_event error paths
# ---------------------------------------------------------------------------


class _FailingEnforcement(PolicyEnforcementClient):
    """Enforcement client that always raises - covers line 199-200 (exc wrap)."""

    async def evaluate(self, tenant_id: UUID, action: dict):  # type: ignore[override]
        raise RuntimeError("simulated upstream outage")


@pytest.mark.asyncio
async def test_ingest_wraps_enforcement_failure():
    """Enforcement client exception -> IngestServiceError with the cause."""
    bp = DefaultBundleProvider()
    kp = InMemorySigningKeyProvider()
    ec = _FailingEnforcement()
    session = _mock_session()
    with pytest.raises(IngestServiceError, match="policy enforcement failed"):
        await ingest_event(
            session=session,
            event=_event(),
            enforcement_client=ec,
            bundle_provider=bp,
            signing_key_provider=kp,
        )


class _DriftingEnforcement(PolicyEnforcementClient):
    """Returns a verdict bound to a DIFFERENT bundle than the active one
    - covers line 203 (bundle drift refuse)."""

    def __init__(self) -> None:
        # Build a stand-alone bundle to bind verdicts under; different id from
        # whatever the DefaultBundleProvider will return.
        self._other_bundle = build_bundle(
            tenant_id=uuid4(),
            version="0.0.0",
            content={"rules": [{"kind": "x", "decision": "allow"}], "default": "allow"},
        )
        self._client = MockLobsterTrapClient(
            policy_bundle_id=self._other_bundle.id,
            policy_bundle_version=self._other_bundle.version,
            content=self._other_bundle.content,
        )

    async def evaluate(self, tenant_id: UUID, action: dict):  # type: ignore[override]
        return await self._client.evaluate(tenant_id, action)


@pytest.mark.asyncio
async def test_ingest_refuses_bundle_drift():
    """If the verdict's bundle_id != active bundle.id, refuse to persist."""
    bp = DefaultBundleProvider()
    kp = InMemorySigningKeyProvider()
    ec = _DriftingEnforcement()
    session = _mock_session()
    with pytest.raises(IngestServiceError, match="different bundle"):
        await ingest_event(
            session=session,
            event=_event(),
            enforcement_client=ec,
            bundle_provider=bp,
            signing_key_provider=kp,
        )


# ---------------------------------------------------------------------------
# Default provider singletons in routes.events get exercised
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_routes_events_default_providers_callable():
    """Cover the three Depends-factory functions in routes/events.py and the
    LazyDefaultEnforcement evaluate path so that production wire-up isn't
    dead code."""
    from apps.api.routes.events import (
        _LazyDefaultEnforcement,
        get_bundle_provider,
        get_enforcement_client,
        get_signing_key_provider,
    )

    bp = await get_bundle_provider()
    kp = await get_signing_key_provider()
    ec = await get_enforcement_client()
    assert bp is not None
    assert kp is not None
    assert ec is not None
    # Hit the LazyDefaultEnforcement.evaluate path twice with the SAME tenant
    # so the per_bundle cache hit branch fires.
    lazy = _LazyDefaultEnforcement()
    tid = uuid4()
    v1 = await lazy.evaluate(tid, {"kind": "x"})
    v2 = await lazy.evaluate(tid, {"kind": "x"})
    assert v1.policy_bundle_id == v2.policy_bundle_id

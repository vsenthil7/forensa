"""Unit tests for apps.api.ingest_service (CP9.11)."""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from apps.api.ingest_service import (
    DefaultBundleProvider,
    IngestServiceError,
    InMemorySigningKeyProvider,
    PostgresBundleProvider,
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


# ---------------------------------------------------------------------------
# PostgresBundleProvider (CP9.14 / NEW-P9.8.24)
#
# Tests the production-wired bundle provider that reads from / writes to the
# bundle_repository. Uses a tiny async-context-manager session factory that
# yields a MagicMock session shaped like the bundle repo expects (scalar_one_or_none
# for the SELECT, session.add + session.flush for the INSERT fallback path).
# ---------------------------------------------------------------------------


class _AsyncCMSession:
    """Minimal ``async with`` wrapper around a single mock session.

    The provider does ``async with self._session_factory() as session: ...``
    so the factory must be a zero-arg callable that returns an instance of an
    async-context-manager class. This is the test seam.
    """

    def __init__(self, session: MagicMock) -> None:
        self._session = session

    async def __aenter__(self) -> MagicMock:
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


def _bundle_session_factory(
    *,
    existing_bundle_row=None,
) -> tuple[Callable[[], _AsyncCMSession], MagicMock]:
    """Return (factory, the_one_session_the_factory_yields).

    The factory is a zero-arg callable that returns an _AsyncCMSession
    wrapping a single shared mock session. Tests can then inspect
    ``session.add.call_args`` etc. after the provider call.
    """
    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=existing_bundle_row)
    session = MagicMock()
    session.execute = AsyncMock(return_value=result_mock)
    session.add = MagicMock()
    session.flush = AsyncMock(return_value=None)

    def factory() -> _AsyncCMSession:
        return _AsyncCMSession(session)

    return factory, session


@pytest.mark.asyncio
async def test_postgres_bundle_provider_returns_existing_bundle():
    """Repository has a bundle for this tenant -> provider returns it WITHOUT
    building or persisting a new one."""
    from packages.ledger.models import PolicyBundleRow

    tid = uuid4()
    existing_bundle = build_bundle(
        tenant_id=tid,
        version="2.5.1",
        content={"rules": [{"kind": "x", "decision": "allow"}], "default": "allow"},
    )
    row = MagicMock(spec=PolicyBundleRow)
    row.id = existing_bundle.id
    row.tenant_id = existing_bundle.tenant_id
    row.version = existing_bundle.version
    row.content_hash = existing_bundle.content_hash
    row.content = existing_bundle.content
    row.created_at = existing_bundle.created_at

    factory, session = _bundle_session_factory(existing_bundle_row=row)
    provider = PostgresBundleProvider(factory)
    found = await provider.get_active_bundle(tid)

    assert found.id == existing_bundle.id
    assert found.version == "2.5.1"
    assert found.tenant_id == tid
    # Must NOT have persisted anything on the hit path.
    session.add.assert_not_called()
    session.flush.assert_not_called()


@pytest.mark.asyncio
async def test_postgres_bundle_provider_persists_default_on_cache_miss():
    """Repository returns no row -> provider builds default bundle AND
    persists it via write_bundle so subsequent calls return the same id.

    Uses ``auto_activate=False`` to exercise the persistence path in
    isolation; the auto_activate workflow path is tested separately.
    """
    tid = uuid4()
    factory, session = _bundle_session_factory(existing_bundle_row=None)
    provider = PostgresBundleProvider(factory, auto_activate=False)
    bundle = await provider.get_active_bundle(tid)

    assert bundle.tenant_id == tid
    assert bundle.version == "1.0.0"
    # write_bundle calls session.add(row) then session.flush()
    assert session.add.call_count == 1
    persisted = session.add.call_args[0][0]
    assert persisted.tenant_id == tid
    assert persisted.id == bundle.id
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_postgres_bundle_provider_uses_custom_fallback_content():
    """Constructor accepts a ``fallback_content`` override which is used in
    place of ``DefaultBundleProvider._DEFAULT_CONTENT`` when building the
    cache-miss bundle.

    Uses ``auto_activate=False`` for isolation.
    """
    tid = uuid4()
    factory, _ = _bundle_session_factory(existing_bundle_row=None)
    custom = {"rules": [{"kind": "audit", "decision": "escalate"}], "default": "deny"}
    provider = PostgresBundleProvider(factory, fallback_content=custom, auto_activate=False)
    bundle = await provider.get_active_bundle(tid)
    assert bundle.content == custom


@pytest.mark.asyncio
async def test_postgres_bundle_provider_auto_activates_on_cache_miss():
    """CP9.15: default ``auto_activate=True`` walks the bootstrap bundle
    through propose -> review -> approve -> activate so subsequent
    get_active_bundle calls find it via ``status='active'``.

    Counts the workflow approval rows written (4 transitions = 4 rows) plus
    the bundle row itself = 5 ``session.add`` calls total.

    The mock has to feed ``scalar_one_or_none`` a specific sequence of
    return values because each workflow step calls ``_load_bundle`` and
    ``activate`` additionally queries for a prior-active bundle. The
    sequence is set up explicitly so the test does not rely on
    SQL-introspection heuristics.
    """
    from packages.ledger.models import PolicyBundleApprovalRow, PolicyBundleRow

    tid = uuid4()
    added_rows: list[object] = []

    def _make_bundle_row_view():
        """Return the most recently added PolicyBundleRow (mutable mock).

        The workflow mutates ``bundle.status`` in place between transitions,
        and the mock should reflect that mutation on subsequent reads.
        Since session.add(row) keeps a reference to the same mock instance,
        any in-place mutation by the workflow is visible here automatically.
        """
        for r in reversed(added_rows):
            if isinstance(r, PolicyBundleRow):
                return r
        return None

    # Sequence of scalar_one_or_none returns:
    #   1. None  - get_active_bundle_for_tenant cache miss
    #   2. bundle row - propose: _load_bundle
    #   3. bundle row - review: _load_bundle
    #   4. bundle row - approve: _load_bundle
    #   5. bundle row - activate: _load_bundle (status now 'approved')
    #   6. None  - activate: prior-active lookup (no prior active in this test)
    #   7. bundle row - activate -> _transition -> _load_bundle
    call_sequence = [
        "miss",  # 1
        "bundle",  # 2
        "bundle",  # 3
        "bundle",  # 4
        "bundle",  # 5
        "miss",  # 6
        "bundle",  # 7
    ]
    call_index = {"n": 0}

    def _scalar_returns():
        idx = call_index["n"]
        call_index["n"] += 1
        if idx >= len(call_sequence):
            return _make_bundle_row_view()
        directive = call_sequence[idx]
        return None if directive == "miss" else _make_bundle_row_view()

    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(side_effect=_scalar_returns)
    session = MagicMock()
    session.execute = AsyncMock(return_value=result_mock)
    session.add = MagicMock(side_effect=lambda row: added_rows.append(row))
    session.flush = AsyncMock(return_value=None)

    def factory() -> _AsyncCMSession:
        return _AsyncCMSession(session)

    provider = PostgresBundleProvider(factory, auto_activate=True)
    bundle = await provider.get_active_bundle(tid)

    assert bundle.tenant_id == tid
    # 1 bundle row + 4 approval rows = 5 session.add calls
    bundle_rows = [r for r in added_rows if isinstance(r, PolicyBundleRow)]
    approval_rows = [r for r in added_rows if isinstance(r, PolicyBundleApprovalRow)]
    assert len(bundle_rows) == 1
    assert len(approval_rows) == 4
    # Transitions in order: propose (proposed->proposed), review
    # (proposed->reviewed), approve (reviewed->approved), activate
    # (approved->active).
    transitions = [(a.from_status, a.to_status) for a in approval_rows]
    assert transitions == [
        ("proposed", "proposed"),
        ("proposed", "reviewed"),
        ("reviewed", "approved"),
        ("approved", "active"),
    ]
    # CP9.15.1: each role has a distinct synthetic actor (segregation of
    # duties), so we expect 4 distinct actor_ids across the 4 approval rows.
    actor_ids = {a.actor_id for a in approval_rows}
    assert len(actor_ids) == 4
    assert None not in actor_ids  # synthetic system actors are real UUIDs not None
    # Final bundle row status must be 'active'
    assert bundle_rows[0].status == "active"


# ---------------------------------------------------------------------------
# CP9.18 / BR-02: InMemoryAgentSigningKeyProvider + agent_signing_key_provider
# = None backwards-compat path through ingest_event.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_in_memory_agent_signing_key_provider_returns_32_byte_key():
    """CP9.18: parallel to the tenant signing key provider, keyed by agent_id."""
    from apps.api.ingest_service import InMemoryAgentSigningKeyProvider

    p = InMemoryAgentSigningKeyProvider()
    aid = uuid4()
    key = await p.get_signing_key(aid)
    assert isinstance(key, bytes)
    assert len(key) == 32


@pytest.mark.asyncio
async def test_in_memory_agent_signing_key_provider_caches_per_agent():
    """Same agent_id -> same key bytes (cache hit branch)."""
    from apps.api.ingest_service import InMemoryAgentSigningKeyProvider

    p = InMemoryAgentSigningKeyProvider()
    aid = uuid4()
    k1 = await p.get_signing_key(aid)
    k2 = await p.get_signing_key(aid)
    assert k1 == k2


@pytest.mark.asyncio
async def test_in_memory_agent_signing_key_provider_distinct_per_agent():
    """Different agent_ids -> different keys (no cross-agent collision)."""
    from apps.api.ingest_service import InMemoryAgentSigningKeyProvider

    p = InMemoryAgentSigningKeyProvider()
    a1 = uuid4()
    a2 = uuid4()
    k1 = await p.get_signing_key(a1)
    k2 = await p.get_signing_key(a2)
    assert k1 != k2


@pytest.mark.asyncio
async def test_ingest_event_with_no_agent_signing_key_provider_produces_single_sig_receipt():
    """CP9.18 backwards-compat: ingest_event with agent_signing_key_provider=None
    (the default, the legacy behaviour) calls build_receipt with
    agent_signing_key=None and produces a receipt where agent_signature is None.

    This is the path the route uses today when the auth layer hasn't yet
    resolved an agent's identity (eg. anonymous / system-actor flows). Until
    CP9.18c wires the agent_signing_key_provider through every route, this
    branch is the production fallback.
    """
    bp = DefaultBundleProvider()
    kp = InMemorySigningKeyProvider()
    # Build an enforcement client bound to the same bundle bp returns.
    tid = uuid4()
    bundle = await bp.get_active_bundle(tid)
    ec_client = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )

    class _BoundEnforcement(PolicyEnforcementClient):
        async def evaluate(self, tenant_id: UUID, action: dict):  # type: ignore[override]
            return await ec_client.evaluate(tenant_id, action)

    event = _event(tenant_id=tid)
    session = _mock_session()

    result = await ingest_event(
        session=session,
        event=event,
        enforcement_client=_BoundEnforcement(),
        bundle_provider=bp,
        signing_key_provider=kp,
        # agent_signing_key_provider deliberately omitted - default None.
    )

    # Pull the ReceiptRow that was added to the session and confirm it has
    # NO agent signature (backwards-compat fallback path).
    from packages.ledger.models import ReceiptRow

    receipt_rows = [
        c.args[0] for c in session.add.call_args_list if isinstance(c.args[0], ReceiptRow)
    ]
    assert len(receipt_rows) == 1
    assert receipt_rows[0].agent_signature is None
    # Tenant signature must still be present and 64 bytes.
    assert len(receipt_rows[0].signature) == 64
    # Sanity: the integrity check still passed (chain bind is signature-independent).
    assert result.integrity_ok is True


@pytest.mark.asyncio
async def test_ingest_event_with_agent_signing_key_provider_produces_dual_sig_receipt():
    """CP9.18 happy path: ingest_event with agent_signing_key_provider produces
    a receipt where BOTH signature and agent_signature are populated, signing
    the same receipt_hash."""
    from apps.api.ingest_service import InMemoryAgentSigningKeyProvider

    bp = DefaultBundleProvider()
    kp = InMemorySigningKeyProvider()
    akp = InMemoryAgentSigningKeyProvider()
    tid = uuid4()
    bundle = await bp.get_active_bundle(tid)
    ec_client = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )

    class _BoundEnforcement(PolicyEnforcementClient):
        async def evaluate(self, tenant_id: UUID, action: dict):  # type: ignore[override]
            return await ec_client.evaluate(tenant_id, action)

    event = _event(tenant_id=tid)
    session = _mock_session()

    result = await ingest_event(
        session=session,
        event=event,
        enforcement_client=_BoundEnforcement(),
        bundle_provider=bp,
        signing_key_provider=kp,
        agent_signing_key_provider=akp,
    )

    from packages.ledger.models import ReceiptRow

    receipt_rows = [
        c.args[0] for c in session.add.call_args_list if isinstance(c.args[0], ReceiptRow)
    ]
    assert len(receipt_rows) == 1
    row = receipt_rows[0]
    # Both signatures populated.
    assert row.signature is not None
    assert len(row.signature) == 64
    assert row.agent_signature is not None
    assert len(row.agent_signature) == 64
    # The two signatures are different bytes (different keys, same hash).
    assert row.signature != row.agent_signature
    # Live integrity check still passes - signatures are NOT part of the bind.
    assert result.integrity_ok is True

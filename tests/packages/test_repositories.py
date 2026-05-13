"""Tests for packages/ledger/session.py and packages/ledger/repositories.py.

Strategy: mock AsyncSession so we do not need a live Postgres for unit coverage.
A separate integration test (out of scope for CP4.2) will exercise real
transactions with testcontainers.

Covers:
- _resolve_url: env wins, default fallback
- make_engine: returns AsyncEngine with the resolved URL
- make_sessionmaker: returns callable
- session_scope: commits on success, rolls back on exception, re-raises
- write_event_with_receipt: adds 3 rows in correct order, flushes, returns snap_id
- write_event_with_receipt: rejects policy_bundle_id mismatch
- write_event_with_receipt: rejects tenant_id mismatch
- write_event_with_receipt: rejects event_id mismatch
- get_latest_receipt_for_tenant: returns None when scalar_one_or_none returns None
- get_latest_receipt_for_tenant: reconstructs Receipt from row
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from packages.crypto.sign import generate_keypair
from packages.ledger.models import ReceiptRow
from packages.ledger.receipt_builder import build_receipt
from packages.ledger.repositories import (
    get_latest_receipt_for_tenant,
    write_event_with_receipt,
)
from packages.ledger.session import (
    _DEFAULT_URL,
    _resolve_url,
    make_engine,
    make_sessionmaker,
    session_scope,
)
from packages.policy.bundle_builder import build_bundle
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.policy.snapshot import capture_snapshot
from packages.schema.event import Event
from packages.schema.receipt import Receipt

_TENANT_ID = UUID("88888888-8888-8888-8888-888888888888")
_OTHER_TENANT_ID = UUID("99999999-9999-9999-9999-999999999999")
_AGENT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_SAMPLE_CONTENT = {
    "rules": [{"kind": "deny_kind", "decision": "deny"}],
    "default": "allow",
}


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_event(tenant_id: UUID = _TENANT_ID, event_id: UUID | None = None) -> Event:
    return Event(
        id=event_id if event_id is not None else uuid4(),
        tenant_id=tenant_id,
        agent_id=_AGENT_ID,
        trace_id="a" * 32,
        span_id="b" * 16,
        parent_span_id=None,
        kind="tool_call",
        occurred_at=datetime.now(UTC),
        payload={"action": "send_email"},
        reasoning=None,
        policy_version=None,
        policy_verdict=None,
    )


def _make_triple(tenant_id: UUID = _TENANT_ID):
    """Build an aligned (event, snapshot, receipt) triple for tests."""
    bundle = build_bundle(tenant_id=tenant_id, version="1.0.0", content=_SAMPLE_CONTENT)
    mock = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )
    verdict = _run(mock.evaluate(tenant_id, {"kind": "x"}))
    snap = capture_snapshot(bundle, verdict)
    event = _make_event(tenant_id=tenant_id)
    priv, _ = generate_keypair()
    snap_id_placeholder = uuid4()
    receipt = build_receipt(
        tenant_id=tenant_id,
        event_id=event.id,
        event_payload=event.payload,
        policy_snapshot=snap,
        policy_snapshot_id=snap_id_placeholder,
        prev_receipt=None,
        tenant_signing_key=priv,
    )
    return event, snap, receipt


# ---------- _resolve_url ----------


def test_resolve_url_returns_default_when_env_unset(monkeypatch):
    monkeypatch.delenv("FORENSA_DB_URL", raising=False)
    assert _resolve_url() == _DEFAULT_URL


def test_resolve_url_returns_env_when_set(monkeypatch):
    monkeypatch.setenv("FORENSA_DB_URL", "postgresql+asyncpg://x/y")
    assert _resolve_url() == "postgresql+asyncpg://x/y"


# ---------- make_engine / make_sessionmaker ----------


def test_make_engine_returns_async_engine():
    fake_engine = MagicMock(spec=AsyncEngine)
    with patch(
        "packages.ledger.session.create_async_engine", return_value=fake_engine
    ) as create:
        engine = make_engine("postgresql+asyncpg://x/y")
    assert engine is fake_engine
    create.assert_called_once()
    args, kwargs = create.call_args
    assert args[0] == "postgresql+asyncpg://x/y"
    assert kwargs["pool_size"] == 5
    assert kwargs["max_overflow"] == 10
    assert kwargs["pool_pre_ping"] is True


def test_make_engine_uses_resolve_url_when_url_is_none(monkeypatch):
    monkeypatch.setenv("FORENSA_DB_URL", "postgresql+asyncpg://from-env/db")
    fake_engine = MagicMock(spec=AsyncEngine)
    with patch(
        "packages.ledger.session.create_async_engine", return_value=fake_engine
    ) as create:
        engine = make_engine()
    assert engine is fake_engine
    args, _ = create.call_args
    assert args[0] == "postgresql+asyncpg://from-env/db"


def test_make_sessionmaker_returns_callable():
    fake_engine = MagicMock(spec=AsyncEngine)
    sm = make_sessionmaker(fake_engine)
    assert callable(sm)


# ---------- session_scope ----------


def test_session_scope_commits_on_success():
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    sm = MagicMock(return_value=session)

    async def use():
        async with session_scope(sm) as s:
            assert s is session

    _run(use())
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()


def test_session_scope_rolls_back_and_reraises_on_exception():
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    sm = MagicMock(return_value=session)

    async def use():
        async with session_scope(sm):
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        _run(use())
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()


# ---------- write_event_with_receipt ----------


def test_write_event_with_receipt_adds_three_rows_and_flushes():
    event, snap, receipt = _make_triple()
    session = MagicMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()

    snap_id = _run(write_event_with_receipt(session, event=event, snapshot=snap, receipt=receipt))

    assert isinstance(snap_id, UUID)
    assert session.add.call_count == 3
    added_types = [type(call.args[0]).__name__ for call in session.add.call_args_list]
    assert added_types == ["PolicySnapshotRow", "EventRow", "ReceiptRow"]
    session.flush.assert_awaited_once()


def test_write_rejects_policy_bundle_id_mismatch():
    event, _, receipt = _make_triple()
    other_bundle = build_bundle(tenant_id=_TENANT_ID, version="9.9.9", content={"x": 1})
    other_mock = MockLobsterTrapClient(
        policy_bundle_id=other_bundle.id,
        policy_bundle_version=other_bundle.version,
        content=other_bundle.content,
    )
    other_verdict = _run(other_mock.evaluate(_TENANT_ID, {"kind": "x"}))
    other_snap = capture_snapshot(other_bundle, other_verdict)

    session = MagicMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()

    with pytest.raises(ValueError, match="policy_bundle_id does not match"):
        _run(write_event_with_receipt(session, event=event, snapshot=other_snap, receipt=receipt))
    session.add.assert_not_called()
    session.flush.assert_not_awaited()


def test_write_rejects_tenant_id_mismatch():
    _, snap, receipt = _make_triple()
    other_event = _make_event(tenant_id=_OTHER_TENANT_ID)
    session = MagicMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()

    with pytest.raises(ValueError, match="tenant_id does not match"):
        _run(write_event_with_receipt(session, event=other_event, snapshot=snap, receipt=receipt))
    session.add.assert_not_called()


def test_write_rejects_event_id_mismatch():
    _, snap, receipt = _make_triple()
    different_event = _make_event(tenant_id=_TENANT_ID, event_id=uuid4())
    session = MagicMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()

    with pytest.raises(ValueError, match="event_id does not match"):
        _run(
            write_event_with_receipt(
                session,
                event=different_event,
                snapshot=snap,
                receipt=receipt,
            )
        )
    session.add.assert_not_called()


# ---------- get_latest_receipt_for_tenant ----------


def test_get_latest_receipt_returns_none_when_no_rows():
    session = MagicMock(spec=AsyncSession)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=result_mock)

    result = _run(get_latest_receipt_for_tenant(session, _TENANT_ID))
    assert result is None


def test_get_latest_receipt_reconstructs_receipt_from_row():
    _, _, receipt = _make_triple()
    row = MagicMock(spec=ReceiptRow)
    row.id = receipt.id
    row.tenant_id = receipt.tenant_id
    row.event_id = receipt.event_id
    row.policy_bundle_id = receipt.policy_bundle_id
    row.sequence = receipt.sequence
    row.prev_receipt_hash = receipt.prev_receipt_hash
    row.payload_hash = receipt.payload_hash
    row.receipt_hash = receipt.receipt_hash
    row.signature = receipt.signature
    row.signed_at = receipt.signed_at

    session = MagicMock(spec=AsyncSession)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=result_mock)

    result = _run(get_latest_receipt_for_tenant(session, _TENANT_ID))
    assert isinstance(result, Receipt)
    assert result.receipt_hash == receipt.receipt_hash
    assert result.sequence == receipt.sequence

"""Unit tests for packages.ledger.ma_export_job_repository (CP9.43 / IP #8).

Schema half of NEW-P12.X.ma-export-async-job. The CP9.44 job-runner module
and CP9.45 route layer are separate CPs.

Strategy: mock AsyncSession so we don't need a live Postgres for unit
coverage. PG-marked integration tests at tests/integration/test_ma_export_jobs_pg.py
exercise the real DB.

Covers:
- create_ma_export_job: returns UUID, adds row to session, flushes
- create_ma_export_job: rejects naive timestamps (tzinfo is None)
- create_ma_export_job: rejects inverted scope (scope_end < scope_start)
- get_ma_export_job_by_id: returns None when not found
- get_ma_export_job_by_id: without tenant_id kwarg, SQL omits tenant filter
- get_ma_export_job_by_id: with tenant_id kwarg, SQL has tenant filter (CP9.33)
- get_ma_export_job_by_id: returns row when found
- list_ma_export_jobs_for_tenant: returns rows ordered by requested_at DESC
- mark_pending_to_running: happy path mutates status + started_at
- mark_pending_to_running: raises MaExportJobStateError when row not found
- mark_pending_to_running: raises MaExportJobStateError when status != pending
- mark_running_to_completed: happy path mutates status + result_export + completed_at
- mark_running_to_completed: raises when row not found
- mark_running_to_completed: raises when status is already terminal (completed)
- mark_running_to_completed: raises when status is pending (skipped running)
- mark_failed: happy path from pending
- mark_failed: happy path from running
- mark_failed: raises when row not found
- mark_failed: raises when status is already terminal
- mark_failed: truncates error_message at 2048 chars
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from packages.ledger.ma_export_job_repository import (
    JOB_STATUSES,
    JOB_TERMINAL_STATUSES,
    MaExportJobStateError,
    create_ma_export_job,
    get_ma_export_job_by_id,
    list_ma_export_jobs_for_tenant,
    mark_ma_export_job_failed,
    mark_ma_export_job_pending_to_running,
    mark_ma_export_job_running_to_completed,
)
from packages.ledger.models import MaExportJobRow

_TENANT_ID = UUID("11111111-2222-3333-4444-555555555555")
_OTHER_TENANT_ID = UUID("66666666-7777-8888-9999-aaaaaaaaaaaa")
_AGENT_ID = UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
_SCOPE_START = datetime(2026, 1, 1, tzinfo=UTC)
_SCOPE_END = datetime(2026, 5, 1, tzinfo=UTC)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _mock_session_returning_row(row_or_none) -> MagicMock:
    """Mock AsyncSession whose execute().scalar_one_or_none() returns row_or_none."""
    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=row_or_none)
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result_mock)
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


def _mock_session_returning_scalars(rows: list) -> MagicMock:
    """Mock AsyncSession whose execute().scalars().all() returns rows."""
    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=rows)
    result_mock = MagicMock()
    result_mock.scalars = MagicMock(return_value=scalars_mock)
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=result_mock)
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


def _make_job_row(
    *,
    job_id: UUID | None = None,
    tenant_id: UUID = _TENANT_ID,
    status: str = "pending",
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    result_export: dict | None = None,
    result_error: str | None = None,
) -> MagicMock:
    row = MagicMock(spec=MaExportJobRow)
    row.id = job_id if job_id is not None else uuid4()
    row.tenant_id = tenant_id
    row.status = status
    row.scope_start = _SCOPE_START
    row.scope_end = _SCOPE_END
    row.requested_at = datetime(2026, 5, 15, 14, 0, tzinfo=UTC)
    row.started_at = started_at
    row.completed_at = completed_at
    row.result_export = result_export
    row.result_error = result_error
    row.encrypt_for_pubkey_b64 = None
    row.platform_sign_key_id = None
    row.requested_by_agent_id = None
    return row


# ---------- module-level constants ----------


def test_job_statuses_includes_expected_four() -> None:
    assert JOB_STATUSES == ("pending", "running", "completed", "failed")


def test_terminal_statuses_is_completed_and_failed() -> None:
    assert JOB_TERMINAL_STATUSES == ("completed", "failed")


# ---------- create_ma_export_job ----------


def test_create_job_returns_uuid_and_adds_row() -> None:
    session = _mock_session_returning_row(None)
    job_id = _run(
        create_ma_export_job(
            session,
            tenant_id=_TENANT_ID,
            scope_start=_SCOPE_START,
            scope_end=_SCOPE_END,
        )
    )
    assert isinstance(job_id, UUID)
    assert session.add.call_count == 1
    added = session.add.call_args[0][0]
    assert isinstance(added, MaExportJobRow)
    assert added.id == job_id
    assert added.tenant_id == _TENANT_ID
    assert added.status == "pending"
    assert added.scope_start == _SCOPE_START
    assert added.scope_end == _SCOPE_END
    session.flush.assert_awaited_once()


def test_create_job_carries_optional_kwargs() -> None:
    session = _mock_session_returning_row(None)
    requested_at = datetime(2026, 5, 15, 12, 0, tzinfo=UTC)
    _run(
        create_ma_export_job(
            session,
            tenant_id=_TENANT_ID,
            scope_start=_SCOPE_START,
            scope_end=_SCOPE_END,
            encrypt_for_pubkey_b64="dGVzdA==",
            platform_sign_key_id="platform-key-v1",
            requested_by_agent_id=_AGENT_ID,
            requested_at=requested_at,
        )
    )
    added = session.add.call_args[0][0]
    assert added.encrypt_for_pubkey_b64 == "dGVzdA=="
    assert added.platform_sign_key_id == "platform-key-v1"
    assert added.requested_by_agent_id == _AGENT_ID
    assert added.requested_at == requested_at


def test_create_job_defaults_requested_at_to_now() -> None:
    session = _mock_session_returning_row(None)
    before = datetime.now(UTC) - timedelta(seconds=1)
    _run(
        create_ma_export_job(
            session,
            tenant_id=_TENANT_ID,
            scope_start=_SCOPE_START,
            scope_end=_SCOPE_END,
        )
    )
    after = datetime.now(UTC) + timedelta(seconds=1)
    added = session.add.call_args[0][0]
    assert before <= added.requested_at <= after


def test_create_job_rejects_naive_scope_start() -> None:
    session = _mock_session_returning_row(None)
    naive_start = datetime(2026, 1, 1)  # no tzinfo
    with pytest.raises(MaExportJobStateError, match="timezone-aware"):
        _run(
            create_ma_export_job(
                session,
                tenant_id=_TENANT_ID,
                scope_start=naive_start,
                scope_end=_SCOPE_END,
            )
        )
    session.add.assert_not_called()


def test_create_job_rejects_naive_scope_end() -> None:
    session = _mock_session_returning_row(None)
    naive_end = datetime(2026, 5, 1)  # no tzinfo
    with pytest.raises(MaExportJobStateError, match="timezone-aware"):
        _run(
            create_ma_export_job(
                session,
                tenant_id=_TENANT_ID,
                scope_start=_SCOPE_START,
                scope_end=naive_end,
            )
        )
    session.add.assert_not_called()


def test_create_job_rejects_inverted_scope() -> None:
    session = _mock_session_returning_row(None)
    with pytest.raises(MaExportJobStateError, match="scope_end.*>=.*scope_start"):
        _run(
            create_ma_export_job(
                session,
                tenant_id=_TENANT_ID,
                scope_start=_SCOPE_END,  # swapped
                scope_end=_SCOPE_START,
            )
        )
    session.add.assert_not_called()


# ---------- get_ma_export_job_by_id ----------


def test_get_job_returns_none_when_not_found() -> None:
    session = _mock_session_returning_row(None)
    result = _run(get_ma_export_job_by_id(session, uuid4()))
    assert result is None


def test_get_job_returns_row_when_found() -> None:
    row = _make_job_row()
    session = _mock_session_returning_row(row)
    result = _run(get_ma_export_job_by_id(session, row.id))
    assert result is row


def test_get_job_without_tenant_id_sql_omits_tenant_filter() -> None:
    """Backwards-compat: tenant_id kwarg defaults to None and the SQL
    must NOT contain a tenant filter (no UUID values bound)."""
    session = _mock_session_returning_row(None)
    _run(get_ma_export_job_by_id(session, uuid4()))
    stmt = session.execute.call_args[0][0]
    compiled = stmt.compile()
    assert _TENANT_ID not in compiled.params.values()
    assert _OTHER_TENANT_ID not in compiled.params.values()


def test_get_job_with_tenant_id_sql_has_tenant_filter() -> None:
    """CP9.33 pattern: passing tenant_id adds the SQL filter."""
    session = _mock_session_returning_row(None)
    _run(get_ma_export_job_by_id(session, uuid4(), tenant_id=_TENANT_ID))
    stmt = session.execute.call_args[0][0]
    compiled = stmt.compile()
    assert _TENANT_ID in compiled.params.values()


def test_get_job_cross_tenant_probe_returns_none() -> None:
    """When the mock returns None (the SQL filter would exclude the row),
    the helper returns None (does NOT raise)."""
    session = _mock_session_returning_row(None)
    result = _run(get_ma_export_job_by_id(session, uuid4(), tenant_id=_OTHER_TENANT_ID))
    assert result is None


# ---------- list_ma_export_jobs_for_tenant ----------


def test_list_jobs_empty_returns_empty_list() -> None:
    session = _mock_session_returning_scalars([])
    result = _run(list_ma_export_jobs_for_tenant(session, _TENANT_ID))
    assert result == []


def test_list_jobs_returns_rows() -> None:
    rows = [_make_job_row() for _ in range(3)]
    session = _mock_session_returning_scalars(rows)
    result = _run(list_ma_export_jobs_for_tenant(session, _TENANT_ID))
    assert result == rows


def test_list_jobs_filters_by_tenant_id_in_sql() -> None:
    session = _mock_session_returning_scalars([])
    _run(list_ma_export_jobs_for_tenant(session, _TENANT_ID))
    stmt = session.execute.call_args[0][0]
    compiled = stmt.compile()
    assert _TENANT_ID in compiled.params.values()


def test_list_jobs_applies_limit_and_offset_in_sql() -> None:
    session = _mock_session_returning_scalars([])
    _run(list_ma_export_jobs_for_tenant(session, _TENANT_ID, limit=10, offset=20))
    stmt = session.execute.call_args[0][0]
    sql = str(stmt.compile())
    assert "LIMIT" in sql.upper()
    assert "OFFSET" in sql.upper()


# ---------- mark_pending_to_running ----------


def test_mark_pending_to_running_happy_path() -> None:
    row = _make_job_row(status="pending")
    session = _mock_session_returning_row(row)
    _run(mark_ma_export_job_pending_to_running(session, row.id))
    assert row.status == "running"
    assert row.started_at is not None
    session.flush.assert_awaited_once()


def test_mark_pending_to_running_with_explicit_started_at() -> None:
    row = _make_job_row(status="pending")
    session = _mock_session_returning_row(row)
    explicit_started = datetime(2026, 5, 15, 16, 0, tzinfo=UTC)
    _run(mark_ma_export_job_pending_to_running(session, row.id, started_at=explicit_started))
    assert row.started_at == explicit_started


def test_mark_pending_to_running_raises_when_row_not_found() -> None:
    session = _mock_session_returning_row(None)
    with pytest.raises(MaExportJobStateError, match="not found"):
        _run(mark_ma_export_job_pending_to_running(session, uuid4()))


def test_mark_pending_to_running_raises_when_status_is_running() -> None:
    row = _make_job_row(status="running")
    session = _mock_session_returning_row(row)
    with pytest.raises(MaExportJobStateError, match="pending"):
        _run(mark_ma_export_job_pending_to_running(session, row.id))


def test_mark_pending_to_running_raises_when_status_is_completed() -> None:
    row = _make_job_row(status="completed")
    session = _mock_session_returning_row(row)
    with pytest.raises(MaExportJobStateError, match="pending"):
        _run(mark_ma_export_job_pending_to_running(session, row.id))


# ---------- mark_running_to_completed ----------


def test_mark_running_to_completed_happy_path() -> None:
    row = _make_job_row(status="running")
    session = _mock_session_returning_row(row)
    payload = {"version": "1.0", "summary": {"receipts_total": 100}}
    _run(mark_ma_export_job_running_to_completed(session, row.id, result_export=payload))
    assert row.status == "completed"
    assert row.result_export == payload
    assert row.completed_at is not None
    session.flush.assert_awaited_once()


def test_mark_running_to_completed_raises_when_row_not_found() -> None:
    session = _mock_session_returning_row(None)
    with pytest.raises(MaExportJobStateError, match="not found"):
        _run(mark_ma_export_job_running_to_completed(session, uuid4(), result_export={}))


def test_mark_running_to_completed_raises_when_already_completed() -> None:
    row = _make_job_row(status="completed")
    session = _mock_session_returning_row(row)
    with pytest.raises(MaExportJobStateError, match="terminal"):
        _run(mark_ma_export_job_running_to_completed(session, row.id, result_export={}))


def test_mark_running_to_completed_raises_when_already_failed() -> None:
    row = _make_job_row(status="failed")
    session = _mock_session_returning_row(row)
    with pytest.raises(MaExportJobStateError, match="terminal"):
        _run(mark_ma_export_job_running_to_completed(session, row.id, result_export={}))


def test_mark_running_to_completed_raises_when_still_pending() -> None:
    """Skipping running is rejected even though the row is non-terminal."""
    row = _make_job_row(status="pending")
    session = _mock_session_returning_row(row)
    with pytest.raises(MaExportJobStateError, match="running -> completed"):
        _run(mark_ma_export_job_running_to_completed(session, row.id, result_export={}))


# ---------- mark_failed ----------


def test_mark_failed_from_pending() -> None:
    """Startup failure before work begins: pending -> failed is allowed."""
    row = _make_job_row(status="pending")
    session = _mock_session_returning_row(row)
    _run(mark_ma_export_job_failed(session, row.id, error_message="startup boom"))
    assert row.status == "failed"
    assert row.result_error == "startup boom"
    assert row.completed_at is not None


def test_mark_failed_from_running() -> None:
    row = _make_job_row(status="running")
    session = _mock_session_returning_row(row)
    _run(mark_ma_export_job_failed(session, row.id, error_message="midjob boom"))
    assert row.status == "failed"
    assert row.result_error == "midjob boom"


def test_mark_failed_raises_when_row_not_found() -> None:
    session = _mock_session_returning_row(None)
    with pytest.raises(MaExportJobStateError, match="not found"):
        _run(mark_ma_export_job_failed(session, uuid4(), error_message="x"))


def test_mark_failed_raises_when_already_completed() -> None:
    row = _make_job_row(status="completed")
    session = _mock_session_returning_row(row)
    with pytest.raises(MaExportJobStateError, match="terminal"):
        _run(mark_ma_export_job_failed(session, row.id, error_message="x"))


def test_mark_failed_raises_when_already_failed() -> None:
    row = _make_job_row(status="failed")
    session = _mock_session_returning_row(row)
    with pytest.raises(MaExportJobStateError, match="terminal"):
        _run(mark_ma_export_job_failed(session, row.id, error_message="x"))


def test_mark_failed_truncates_error_message_at_2048_chars() -> None:
    """A runaway traceback can't fill the DB column."""
    row = _make_job_row(status="running")
    session = _mock_session_returning_row(row)
    huge_msg = "x" * 5000
    _run(mark_ma_export_job_failed(session, row.id, error_message=huge_msg))
    assert row.result_error is not None
    assert len(row.result_error) == 2048

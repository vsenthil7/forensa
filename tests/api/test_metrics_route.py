"""Tests for GET /v1/metrics (CP9.59 / API-F15).

Covers:
- Happy path: snapshot returns the expected shape with counts derived
  from a mocked session.
- Tenant scoping: tenant_id mismatch with principal → 403.
- Window bounds: window_hours validated; defaults to 24.
- Empty tenant: receipts_total=0 and chain_head_sequence=None when no
  receipts exist.
- The session mock honours WHERE filters by status string for the
  anchor/job count branches.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import create_app
from apps.api.routes.receipts import get_session
from tests.api._auth_helpers import install_principal_override

_TENANT_ID = UUID("33333333-4444-5555-6666-777777777777")
_AGENT_ID = UUID("44444444-5555-6666-7777-888888888888")
_OTHER_TENANT_ID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")


def _build_session_mock(
    *,
    events_total: int = 0,
    events_in_window: int = 0,
    receipts_total: int = 0,
    receipts_in_window: int = 0,
    chain_head: tuple[int, datetime] | None = None,
    anchored_in_window: int = 0,
    deferred_in_window: int = 0,
    jobs_by_status: dict[str, int] | None = None,
):
    """Return a session whose execute() dispatches by the compiled SQL.

    The route issues many small count queries plus one chain-head select.
    We dispatch by inspecting the compiled SQL string for table + status
    filters. This keeps the test schema-aware without booting Postgres.
    """
    jobs_by_status = jobs_by_status or {}
    # Track which count query we're answering by inspecting the SQL.
    call_state = {"event_calls": 0, "receipt_calls": 0}

    async def _execute(stmt):
        sql = str(stmt.compile(compile_kwargs={"literal_binds": False})).lower()

        # Chain head select (returns a (sequence, signed_at) tuple via .first()).
        # Detected by presence of "order by receipts.sequence desc" and the
        # absence of count().
        if "order by receipts.sequence desc" in sql:
            result = MagicMock()
            if chain_head is None:
                result.first = MagicMock(return_value=None)
            else:
                # SQLAlchemy returns a Row whose [0],[1] indexing works.
                row = MagicMock()
                row.__getitem__ = lambda _self, i: chain_head[i]
                result.first = MagicMock(return_value=row)
            return result

        # All remaining queries are SELECT count() ... returning a scalar.
        # We use the table name + (optionally) the status filter to pick
        # which fixture count to return.
        params = stmt.compile().params

        if "from events" in sql:
            # First event-count call is "total"; second is "in window".
            call_state["event_calls"] += 1
            count = events_total if call_state["event_calls"] == 1 else events_in_window
        elif "from receipts" in sql:
            call_state["receipt_calls"] += 1
            count = receipts_total if call_state["receipt_calls"] == 1 else receipts_in_window
        elif "from timestamp_anchors" in sql:
            # Branch by status filter param.
            status_filter = next(
                (v for k, v in params.items() if isinstance(v, str) and v in ("anchored", "deferred")),
                None,
            )
            count = anchored_in_window if status_filter == "anchored" else deferred_in_window
        elif "from ma_export_jobs" in sql:
            status_filter = next(
                (
                    v
                    for k, v in params.items()
                    if isinstance(v, str) and v in ("pending", "running", "completed", "failed")
                ),
                None,
            )
            count = jobs_by_status.get(status_filter, 0)
        else:  # pragma: no cover - any new count query needs explicit support
            count = 0

        result = MagicMock()
        result.scalar_one = MagicMock(return_value=count)
        return result

    session = MagicMock()
    session.execute = AsyncMock(side_effect=_execute)

    async def _override():
        return session

    return _override


@pytest.fixture
def app():
    a = create_app()
    install_principal_override(a, tenant_id=_TENANT_ID, agent_id=_AGENT_ID)
    return a


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_metrics_happy_path_returns_full_snapshot(app, client) -> None:
    app.dependency_overrides[get_session] = _build_session_mock(
        events_total=120,
        events_in_window=48,
        receipts_total=120,
        receipts_in_window=48,
        chain_head=(119, datetime(2026, 5, 18, 14, 0, tzinfo=UTC)),
        anchored_in_window=1,
        deferred_in_window=0,
        jobs_by_status={"completed": 2, "pending": 1, "running": 0, "failed": 0},
    )
    response = await client.get(f"/v1/metrics?tenant_id={_TENANT_ID}")
    assert response.status_code == 200, response.text
    body = response.json()
    # Shape
    assert body["tenant_id"] == str(_TENANT_ID)
    assert body["window_hours"] == 24
    assert body["window_start"] < body["window_end"]
    # Ingest
    assert body["ingest"]["events_total"] == 120
    assert body["ingest"]["events_in_window"] == 48
    assert body["ingest"]["events_per_hour"] == 2.0
    # Signing
    assert body["signing"]["receipts_total"] == 120
    assert body["signing"]["chain_head_sequence"] == 119
    assert body["signing"]["last_receipt_signed_at"] is not None
    # Anchoring
    assert body["anchoring"]["anchors_in_window"] == 1
    assert body["anchoring"]["anchored"] == 1
    assert body["anchoring"]["deferred"] == 0
    # M&A jobs
    assert body["ma_export_jobs"]["completed"] == 2
    assert body["ma_export_jobs"]["pending"] == 1
    assert body["ma_export_jobs"]["running"] == 0
    assert body["ma_export_jobs"]["failed"] == 0


@pytest.mark.asyncio
async def test_metrics_respects_custom_window_hours(app, client) -> None:
    app.dependency_overrides[get_session] = _build_session_mock(
        events_total=600,
        events_in_window=300,
        receipts_total=600,
        receipts_in_window=300,
        chain_head=None,
    )
    response = await client.get(f"/v1/metrics?tenant_id={_TENANT_ID}&window_hours=6")
    assert response.status_code == 200
    body = response.json()
    assert body["window_hours"] == 6
    assert body["ingest"]["events_per_hour"] == 50.0
    assert body["signing"]["receipts_per_hour"] == 50.0


@pytest.mark.asyncio
async def test_metrics_empty_tenant_returns_none_chain_head(app, client) -> None:
    app.dependency_overrides[get_session] = _build_session_mock(
        events_total=0,
        events_in_window=0,
        receipts_total=0,
        receipts_in_window=0,
        chain_head=None,
    )
    response = await client.get(f"/v1/metrics?tenant_id={_TENANT_ID}")
    assert response.status_code == 200
    body = response.json()
    assert body["signing"]["receipts_total"] == 0
    assert body["signing"]["chain_head_sequence"] is None
    assert body["signing"]["last_receipt_signed_at"] is None
    assert body["ingest"]["events_per_hour"] == 0.0


@pytest.mark.asyncio
async def test_metrics_tenant_mismatch_returns_403(app, client) -> None:
    app.dependency_overrides[get_session] = _build_session_mock()
    response = await client.get(f"/v1/metrics?tenant_id={_OTHER_TENANT_ID}")
    assert response.status_code == 403
    body = response.json()
    assert body["detail"]["error"] == "tenant_mismatch"


@pytest.mark.asyncio
async def test_metrics_window_hours_too_small_returns_422(app, client) -> None:
    app.dependency_overrides[get_session] = _build_session_mock()
    response = await client.get(f"/v1/metrics?tenant_id={_TENANT_ID}&window_hours=0")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_metrics_window_hours_too_large_returns_422(app, client) -> None:
    app.dependency_overrides[get_session] = _build_session_mock()
    response = await client.get(
        f"/v1/metrics?tenant_id={_TENANT_ID}&window_hours=169"
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_metrics_deferred_anchors_show_separately(app, client) -> None:
    """A FreeTSA failure leaves a row with status='deferred'; the metrics
    snapshot must surface that separately so the operator sees the
    canonical "we tried, but no TSA timestamp this day" signal."""
    app.dependency_overrides[get_session] = _build_session_mock(
        anchored_in_window=0,
        deferred_in_window=1,
    )
    response = await client.get(f"/v1/metrics?tenant_id={_TENANT_ID}")
    assert response.status_code == 200
    body = response.json()
    assert body["anchoring"]["anchored"] == 0
    assert body["anchoring"]["deferred"] == 1
    assert body["anchoring"]["anchors_in_window"] == 1


@pytest.mark.asyncio
async def test_metrics_ma_jobs_all_statuses_visible(app, client) -> None:
    app.dependency_overrides[get_session] = _build_session_mock(
        jobs_by_status={"pending": 3, "running": 2, "completed": 5, "failed": 1},
    )
    response = await client.get(f"/v1/metrics?tenant_id={_TENANT_ID}")
    assert response.status_code == 200
    body = response.json()
    assert body["ma_export_jobs"] == {
        "pending": 3,
        "running": 2,
        "completed": 5,
        "failed": 1,
    }

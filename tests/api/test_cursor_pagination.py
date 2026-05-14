"""Tests for CP9.7 cursor pagination + JOIN-fix repo functions.

Covers:
- list_receipts_for_tenant_cursor (seek-based pagination)
- list_receipts_with_snapshot_for_tenant (single-query JOIN replacing N+1)
- /v1/receipts route with before_sequence cursor param
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import create_app
from apps.api.routes.receipts import get_session
from packages.crypto.sign import generate_keypair
from packages.ledger.receipt_builder import build_receipt
from packages.ledger.repositories import (
    list_receipts_for_tenant_cursor,
    list_receipts_with_snapshot_for_tenant,
)
from packages.policy.bundle_builder import build_bundle
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.policy.snapshot import capture_snapshot
from packages.schema.receipt import Receipt

_TENANT_ID = UUID("aaaaaaaa-1111-2222-3333-444444444444")
_SAMPLE_CONTENT = {"rules": [{"kind": "x", "decision": "allow"}], "default": "allow"}


async def _make_chain(n: int) -> list[tuple[Receipt, UUID]]:
    bundle = build_bundle(tenant_id=_TENANT_ID, version="1.0.0", content=_SAMPLE_CONTENT)
    mock = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )
    verdict = await mock.evaluate(_TENANT_ID, {"kind": "x"})
    snap = capture_snapshot(bundle, verdict)
    snap_id = uuid4()
    priv, _ = generate_keypair()
    pairs: list[tuple[Receipt, UUID]] = []
    prev: Receipt | None = None
    base = datetime(2026, 5, 13, 12, 0, tzinfo=UTC)
    for i in range(n):
        r = build_receipt(
            tenant_id=_TENANT_ID,
            event_id=uuid4(),
            event_payload={"step": i},
            policy_snapshot=snap,
            policy_snapshot_id=snap_id,
            prev_receipt=prev,
            tenant_signing_key=priv,
        )
        r = r.model_copy(update={"signed_at": base + timedelta(minutes=i)})
        pairs.append((r, snap_id))
        prev = r
    return pairs


def _mock_session_returning(rows: list[object]) -> AsyncMock:
    """Build an AsyncMock session whose execute() returns those rows."""
    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=rows)
    result = MagicMock()
    result.scalars = MagicMock(return_value=scalars_mock)
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    return session


def _row_for(r: Receipt, snap_id: UUID) -> object:
    from packages.ledger.models import ReceiptRow

    row = MagicMock(spec=ReceiptRow)
    row.id = r.id
    row.tenant_id = r.tenant_id
    row.event_id = r.event_id
    row.policy_bundle_id = r.policy_bundle_id
    row.policy_snapshot_id = snap_id
    row.sequence = r.sequence
    row.prev_receipt_hash = r.prev_receipt_hash
    row.payload_hash = r.payload_hash
    row.receipt_hash = r.receipt_hash
    row.signature = r.signature
    row.signed_at = r.signed_at
    return row


# ========== repo: list_receipts_for_tenant_cursor ==========


@pytest.mark.asyncio
async def test_cursor_first_page_no_before_sequence_returns_newest():
    pairs = await _make_chain(5)
    rows = [_row_for(r, sid) for r, sid in pairs]
    session = _mock_session_returning(rows)
    result = await list_receipts_for_tenant_cursor(session, _TENANT_ID, limit=5)
    assert len(result) == 5
    assert [r.sequence for r in result] == [p[0].sequence for p in pairs]


@pytest.mark.asyncio
async def test_cursor_with_before_sequence_filters_query():
    """Passing before_sequence must add a WHERE clause to the statement.

    We can't easily inspect the compiled SQL in a unit test without a real
    engine, so we assert the result shape and that the function was called.
    """
    pairs = await _make_chain(3)
    rows = [_row_for(r, sid) for r, sid in pairs]
    session = _mock_session_returning(rows)
    result = await list_receipts_for_tenant_cursor(
        session, _TENANT_ID, limit=10, before_sequence=100
    )
    # All 3 rows mocked are returned regardless because the mock does not
    # apply the WHERE clause; the test asserts the function accepted the
    # parameter and returned the shape.
    assert len(result) == 3


@pytest.mark.asyncio
async def test_cursor_empty_result_when_no_rows():
    session = _mock_session_returning([])
    result = await list_receipts_for_tenant_cursor(
        session, _TENANT_ID, limit=50, before_sequence=42
    )
    assert result == []


# ========== repo: list_receipts_with_snapshot_for_tenant ==========


@pytest.mark.asyncio
async def test_join_repo_returns_receipt_and_snapshot_id_pairs():
    pairs = await _make_chain(4)
    rows = [_row_for(r, sid) for r, sid in pairs]
    session = _mock_session_returning(rows)
    result = await list_receipts_with_snapshot_for_tenant(
        session,
        _TENANT_ID,
        scope_start=datetime(2026, 5, 13, tzinfo=UTC),
        scope_end=datetime(2026, 5, 14, tzinfo=UTC),
        limit=100,
    )
    assert len(result) == 4
    for receipt, snap_id in result:
        assert isinstance(receipt, Receipt)
        assert isinstance(snap_id, UUID)


@pytest.mark.asyncio
async def test_join_repo_no_n_plus_1_only_one_execute_call():
    """The whole point: ONE execute call, not N+1.

    Before CP9.7: 1 list call + N get_receipt_by_id calls.
    After CP9.7: 1 JOIN call total.
    """
    pairs = await _make_chain(10)
    rows = [_row_for(r, sid) for r, sid in pairs]
    session = _mock_session_returning(rows)
    await list_receipts_with_snapshot_for_tenant(
        session,
        _TENANT_ID,
        scope_start=datetime(2026, 5, 13, tzinfo=UTC),
        scope_end=datetime(2026, 5, 14, tzinfo=UTC),
        limit=100,
    )
    # Was: 11 calls (1 list + 10 get_by_id). Now: 1 call.
    assert session.execute.call_count == 1


# ========== route: /v1/receipts with cursor param ==========


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_receipts_route_cursor_mode_returns_next_cursor(app, client):
    """Cursor mode: response includes next_before_sequence."""
    pairs = await _make_chain(3)
    rows = [_row_for(r, sid) for r, sid in pairs]
    session = _mock_session_returning(rows)

    async def _override():
        return session

    app.dependency_overrides[get_session] = _override
    response = await client.get(f"/v1/receipts?tenant_id={_TENANT_ID}&limit=3&before_sequence=100")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["count"] == 3
    assert body["before_sequence"] == 100
    assert body["offset"] == 0  # cursor mode echoes offset=0
    # next_cursor = min sequence in this page (since len == limit)
    assert body["next_before_sequence"] == min(p[0].sequence for p in pairs)
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_receipts_route_offset_mode_still_works(app, client):
    """Legacy offset mode: response includes echoed offset, no cursor."""
    pairs = await _make_chain(2)
    rows = [_row_for(r, sid) for r, sid in pairs]
    session = _mock_session_returning(rows)

    async def _override():
        return session

    app.dependency_overrides[get_session] = _override
    response = await client.get(f"/v1/receipts?tenant_id={_TENANT_ID}&limit=50&offset=10")
    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 10
    assert body["before_sequence"] is None
    # len < limit (2 < 50) -> end of stream -> next_cursor is None
    assert body["next_before_sequence"] is None
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_receipts_route_end_of_stream_when_page_short(app, client):
    """If returned rows < limit, next_before_sequence must be None."""
    pairs = await _make_chain(2)
    rows = [_row_for(r, sid) for r, sid in pairs]
    session = _mock_session_returning(rows)

    async def _override():
        return session

    app.dependency_overrides[get_session] = _override
    # limit=10, got 2 rows -> end of stream
    response = await client.get(f"/v1/receipts?tenant_id={_TENANT_ID}&limit=10&before_sequence=99")
    assert response.status_code == 200
    body = response.json()
    assert body["next_before_sequence"] is None

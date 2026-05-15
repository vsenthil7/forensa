"""Tests for GET /v1/anchors REST endpoint (CP9.22).

Exposes the TimestampAnchorRow surface from CP9.19 so investigators can
list a tenant's TSA-anchored days through the API rather than reading
the DB directly.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import create_app
from apps.api.routes.receipts import get_session
from tests.api._auth_helpers import install_principal_override

_TENANT_ID = UUID("77777777-8888-9999-aaaa-bbbbbbbbbbbb")
_AGENT_ID = UUID("88888888-9999-aaaa-bbbb-cccccccccccc")


def _make_anchor_row(
    *,
    tenant_id: UUID = _TENANT_ID,
    anchor_date: datetime,
    status: str = "anchored",
    root_hash: str | None = "a" * 64,
    tsa_identifier: str = "mock-tsa",
    tsr_bytes: bytes | None = b"\x00\x01\x02",
    tsa_signature: bytes | None = b"\xff" * 32,
    timestamped_at: datetime | None = None,
    anchored_at: datetime | None = None,
) -> object:
    from packages.ledger.models import TimestampAnchorRow

    row = MagicMock(spec=TimestampAnchorRow)
    row.id = uuid4()
    row.tenant_id = tenant_id
    row.anchor_date = anchor_date
    row.status = status
    row.root_hash = root_hash if status == "anchored" else None
    row.tsa_identifier = tsa_identifier
    row.tsr_bytes = tsr_bytes if status == "anchored" else None
    row.tsa_signature = tsa_signature if status == "anchored" else None
    row.timestamped_at = timestamped_at or (anchor_date if status == "anchored" else None)
    row.anchored_at = anchored_at or anchor_date
    return row


def _override_session_with_rows(rows: list[object]):
    """Override get_session with a mock returning the provided rows.

    The mock honours the WHERE clause's anchor_date BETWEEN bounds and
    tenant_id filter, returning only rows that match. ORDER BY is applied
    in Python because the mock can't introspect the compiled .order_by.
    """

    async def _execute(stmt):
        try:
            compiled = stmt.compile()
            params = compiled.params
        except Exception:  # pragma: no cover - defensive
            params = {}
        # Window bounds (if both since+until are present, they're in params).
        bounds = [v for v in params.values() if isinstance(v, datetime)]
        # Tenant filter: TenantId param in compiled statement (UUID).
        tenant_filter = next((v for v in params.values() if isinstance(v, UUID)), None)
        filtered = list(rows)
        if tenant_filter is not None:
            filtered = [r for r in filtered if r.tenant_id == tenant_filter]
        if len(bounds) >= 1:
            lo = min(bounds)
            hi = max(bounds)
            if lo == hi:
                # Only one tz-aware bound was provided; treat it as a lower bound.
                filtered = [r for r in filtered if r.anchor_date >= lo]
            else:
                filtered = [r for r in filtered if lo <= r.anchor_date <= hi]
        # Apply DESC order on anchor_date.
        filtered.sort(key=lambda r: r.anchor_date, reverse=True)
        scalars_mock = MagicMock()
        scalars_mock.all = MagicMock(return_value=filtered)
        result = MagicMock()
        result.scalars = MagicMock(return_value=scalars_mock)
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
async def test_list_anchors_returns_anchored_rows(app, client) -> None:
    rows = [
        _make_anchor_row(anchor_date=datetime(2026, 5, 13, tzinfo=UTC)),
        _make_anchor_row(anchor_date=datetime(2026, 5, 14, tzinfo=UTC)),
    ]
    app.dependency_overrides[get_session] = _override_session_with_rows(rows)
    response = await client.get(f"/v1/anchors?tenant_id={_TENANT_ID}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tenant_id"] == str(_TENANT_ID)
    assert body["count"] == 2
    assert len(body["items"]) == 2
    # DESC ordering by anchor_date: 14 May before 13 May.
    dates = [item["anchor_date"] for item in body["items"]]
    assert dates == sorted(dates, reverse=True)
    # Anchored items must have base64 tsr_bytes + signature + non-null root_hash.
    for item in body["items"]:
        assert item["status"] == "anchored"
        assert item["root_hash"] is not None
        assert item["tsr_bytes_b64"] is not None
        assert item["tsa_signature_b64"] is not None
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_anchors_returns_deferred_with_nulls(app, client) -> None:
    rows = [
        _make_anchor_row(anchor_date=datetime(2026, 5, 13, tzinfo=UTC), status="deferred"),
    ]
    app.dependency_overrides[get_session] = _override_session_with_rows(rows)
    response = await client.get(f"/v1/anchors?tenant_id={_TENANT_ID}")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    item = body["items"][0]
    assert item["status"] == "deferred"
    assert item["root_hash"] is None
    assert item["tsr_bytes_b64"] is None
    assert item["tsa_signature_b64"] is None
    assert item["timestamped_at"] is None
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_anchors_empty_returns_zero_count(app, client) -> None:
    app.dependency_overrides[get_session] = _override_session_with_rows([])
    response = await client.get(f"/v1/anchors?tenant_id={_TENANT_ID}")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 0
    assert body["items"] == []
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_anchors_blocks_cross_tenant_with_403(app, client) -> None:
    other = UUID("99999999-aaaa-bbbb-cccc-dddddddddddd")
    app.dependency_overrides[get_session] = _override_session_with_rows([])
    response = await client.get(f"/v1/anchors?tenant_id={other}")
    assert response.status_code == 403
    body = response.json()
    assert body["detail"]["error"] == "tenant_mismatch"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_anchors_rejects_naive_since(app, client) -> None:
    app.dependency_overrides[get_session] = _override_session_with_rows([])
    response = await client.get(f"/v1/anchors?tenant_id={_TENANT_ID}&since=2026-05-13T00:00:00")
    assert response.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_anchors_rejects_naive_until(app, client) -> None:
    app.dependency_overrides[get_session] = _override_session_with_rows([])
    response = await client.get(f"/v1/anchors?tenant_id={_TENANT_ID}&until=2026-05-14T00:00:00")
    assert response.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_anchors_rejects_inverted_window(app, client) -> None:
    app.dependency_overrides[get_session] = _override_session_with_rows([])
    response = await client.get(
        f"/v1/anchors?tenant_id={_TENANT_ID}"
        "&since=2026-05-14T00:00:00%2B00:00"
        "&until=2026-05-13T00:00:00%2B00:00"
    )
    assert response.status_code == 422
    assert "since" in response.json()["detail"]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_anchors_window_filters_rows(app, client) -> None:
    rows = [
        _make_anchor_row(anchor_date=datetime(2026, 5, 12, tzinfo=UTC)),
        _make_anchor_row(anchor_date=datetime(2026, 5, 13, tzinfo=UTC)),
        _make_anchor_row(anchor_date=datetime(2026, 5, 14, tzinfo=UTC)),
        _make_anchor_row(anchor_date=datetime(2026, 5, 15, tzinfo=UTC)),
    ]
    app.dependency_overrides[get_session] = _override_session_with_rows(rows)
    response = await client.get(
        f"/v1/anchors?tenant_id={_TENANT_ID}"
        "&since=2026-05-13T00:00:00%2B00:00"
        "&until=2026-05-14T23:59:59%2B00:00"
    )
    assert response.status_code == 200
    body = response.json()
    # 13 + 14 in window; 12 + 15 out.
    assert body["count"] == 2
    dates = [item["anchor_date"][:10] for item in body["items"]]
    assert set(dates) == {"2026-05-13", "2026-05-14"}
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_anchors_rejects_limit_zero(app, client) -> None:
    app.dependency_overrides[get_session] = _override_session_with_rows([])
    response = await client.get(f"/v1/anchors?tenant_id={_TENANT_ID}&limit=0")
    assert response.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_anchors_rejects_limit_over_max(app, client) -> None:
    app.dependency_overrides[get_session] = _override_session_with_rows([])
    response = await client.get(f"/v1/anchors?tenant_id={_TENANT_ID}&limit=201")
    assert response.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_anchors_rejects_negative_offset(app, client) -> None:
    app.dependency_overrides[get_session] = _override_session_with_rows([])
    response = await client.get(f"/v1/anchors?tenant_id={_TENANT_ID}&offset=-1")
    assert response.status_code == 422
    app.dependency_overrides.clear()

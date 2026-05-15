"""Tests for POST /v1/exports/ma-diligence (CP9.28 / BR-13)."""

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
from packages.policy.bundle_builder import build_bundle
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.policy.snapshot import capture_snapshot
from packages.schema.receipt import Receipt
from tests.api._auth_helpers import install_principal_override

_TENANT = UUID("cccccccc-dddd-eeee-ffff-000000000000")
_OTHER_TENANT = UUID("eeeeeeee-ffff-0000-1111-222222222222")
_AGENT = UUID("dddddddd-eeee-ffff-0000-111111111111")
_CONTENT = {"rules": [{"kind": "x", "decision": "allow"}], "default": "allow"}


async def _make_chain_for_day(n: int, day: datetime) -> list[tuple[Receipt, UUID]]:
    bundle = build_bundle(tenant_id=_TENANT, version="1.0.0", content=_CONTENT)
    mock = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )
    verdict = await mock.evaluate(_TENANT, {"kind": "x"})
    snap = capture_snapshot(bundle, verdict)
    snap_id = uuid4()
    priv, _ = generate_keypair()
    pairs: list[tuple[Receipt, UUID]] = []
    prev: Receipt | None = None
    for i in range(n):
        r = build_receipt(
            tenant_id=_TENANT,
            event_id=uuid4(),
            event_payload={"step": i},
            policy_snapshot=snap,
            policy_snapshot_id=snap_id,
            prev_receipt=prev,
            tenant_signing_key=priv,
        )
        r = r.model_copy(update={"signed_at": day + timedelta(hours=12, minutes=i)})
        pairs.append((r, snap_id))
        prev = r
    return pairs


def _make_receipt_row(r: Receipt, snap_id: UUID) -> object:
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
    row.agent_signature = None
    row.signed_at = r.signed_at
    return row


def _make_anchor_row(anchor_date: datetime, status: str = "anchored") -> object:
    from packages.ledger.models import TimestampAnchorRow

    row = MagicMock(spec=TimestampAnchorRow)
    row.id = uuid4()
    row.tenant_id = _TENANT
    row.anchor_date = anchor_date
    row.status = status
    row.root_hash = ("a" * 64) if status == "anchored" else None
    row.tsa_identifier = "mock-tsa"
    row.tsr_bytes = b"\x00\x01\x02" if status == "anchored" else None
    row.tsa_signature = (b"\xff" * 32) if status == "anchored" else None
    row.timestamped_at = anchor_date.replace(hour=23, minute=59) if status == "anchored" else None
    row.anchored_at = anchor_date.replace(hour=23, minute=59, second=59)
    return row


def _override_session_with_anchors_and_receipts(
    anchor_rows: list[object],
    receipts_by_day: dict[datetime, list[tuple[Receipt, UUID]]],
):
    """Mock session that returns:
    - anchor_rows for the anchors query (one execute call)
    - receipts_by_day[anchor_date] for each subsequent receipts query

    The receipts query is discriminated by reading the WHERE-clause bounds
    out of the compiled SQL; we match the chunk_start day against the keys.
    """
    receipt_rows_by_day = {
        d: [_make_receipt_row(r, sid) for r, sid in pairs] for d, pairs in receipts_by_day.items()
    }

    async def _execute(stmt):
        sql_str = str(stmt).lower()
        if "timestamp_anchors" in sql_str:
            scalars_mock = MagicMock()
            scalars_mock.all = MagicMock(return_value=anchor_rows)
            result = MagicMock()
            result.scalars = MagicMock(return_value=scalars_mock)
            return result
        # Receipts query: extract the chunk_start datetime from the compiled
        # params and look up the matching day's receipts.
        try:
            compiled = stmt.compile()
            params = compiled.params
        except Exception:  # pragma: no cover - defensive
            params = {}
        datetimes = [v for v in params.values() if isinstance(v, datetime)]
        # The chunk_start is the EARLIER bound; receipts_by_day is keyed
        # by day-start. Match the earliest datetime in params against the keys.
        rows: list[object] = []
        if datetimes:
            chunk_start = min(datetimes).replace(hour=0, minute=0, second=0, microsecond=0)
            rows = receipt_rows_by_day.get(chunk_start, [])
        scalars_mock = MagicMock()
        scalars_mock.all = MagicMock(return_value=rows)
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
    install_principal_override(a, tenant_id=_TENANT, agent_id=_AGENT)
    return a


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _request_body(
    *,
    tenant_id: UUID = _TENANT,
    scope_start: str = "2026-05-13T00:00:00+00:00",
    scope_end: str = "2026-05-15T23:59:59+00:00",
) -> dict:
    return {
        "tenant_id": str(tenant_id),
        "scope_start": scope_start,
        "scope_end": scope_end,
    }


# ---------- happy path ----------


@pytest.mark.asyncio
async def test_ma_export_happy_path_two_anchored_days(app, client) -> None:
    day1 = datetime(2026, 5, 13, tzinfo=UTC)
    day2 = datetime(2026, 5, 14, tzinfo=UTC)
    pairs1 = await _make_chain_for_day(2, day1)
    pairs2 = await _make_chain_for_day(3, day2)
    anchor_rows = [_make_anchor_row(day1), _make_anchor_row(day2)]
    receipts_by_day = {day1: pairs1, day2: pairs2}
    app.dependency_overrides[get_session] = _override_session_with_anchors_and_receipts(
        anchor_rows, receipts_by_day
    )
    response = await client.post("/v1/exports/ma-diligence", json=_request_body())
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["header"]["tenant_id"] == str(_TENANT)
    assert body["header"]["pack_count"] == 2
    assert body["header"]["anchor_count"] == 2
    assert body["header"]["total_receipt_count"] == 5  # 2 + 3
    assert len(body["evidence_packs"]) == 2
    assert len(body["anchor_proofs"]) == 2
    assert len(body["ma_root_hash"]) == 64
    # Each pack has its own root_hash and an embedded anchor.
    for pack in body["evidence_packs"]:
        assert len(pack["root_hash"]) == 64
        assert pack["anchor"] is not None
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ma_export_empty_scope_returns_empty_bundle(app, client) -> None:
    # No anchors in scope -> empty bundle with valid ma_root_hash.
    app.dependency_overrides[get_session] = _override_session_with_anchors_and_receipts([], {})
    response = await client.post("/v1/exports/ma-diligence", json=_request_body())
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["header"]["pack_count"] == 0
    assert body["header"]["total_receipt_count"] == 0
    assert body["evidence_packs"] == []
    assert body["anchor_proofs"] == []
    assert len(body["ma_root_hash"]) == 64
    app.dependency_overrides.clear()


# ---------- authz ----------


@pytest.mark.asyncio
async def test_ma_export_403_when_cross_tenant(app, client) -> None:
    app.dependency_overrides[get_session] = _override_session_with_anchors_and_receipts([], {})
    response = await client.post(
        "/v1/exports/ma-diligence", json=_request_body(tenant_id=_OTHER_TENANT)
    )
    assert response.status_code == 403
    body = response.json()
    assert body["detail"]["error"] == "tenant_mismatch"
    app.dependency_overrides.clear()


# ---------- input validation ----------


@pytest.mark.asyncio
async def test_ma_export_422_when_scope_end_before_scope_start(app, client) -> None:
    app.dependency_overrides[get_session] = _override_session_with_anchors_and_receipts([], {})
    response = await client.post(
        "/v1/exports/ma-diligence",
        json=_request_body(
            scope_start="2026-05-15T00:00:00+00:00",
            scope_end="2026-05-13T00:00:00+00:00",
        ),
    )
    assert response.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ma_export_handles_deferred_anchor_row(app, client) -> None:
    day1 = datetime(2026, 5, 13, tzinfo=UTC)
    # Mix anchored + deferred to ensure deferred-tombstone rows bundle cleanly.
    anchor_rows = [
        _make_anchor_row(day1, status="anchored"),
        _make_anchor_row(datetime(2026, 5, 14, tzinfo=UTC), status="deferred"),
    ]
    pairs1 = await _make_chain_for_day(1, day1)
    receipts_by_day = {day1: pairs1}
    app.dependency_overrides[get_session] = _override_session_with_anchors_and_receipts(
        anchor_rows, receipts_by_day
    )
    response = await client.post("/v1/exports/ma-diligence", json=_request_body())
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["header"]["anchor_count"] == 2
    statuses = {a["status"] for a in body["anchor_proofs"]}
    assert statuses == {"anchored", "deferred"}
    app.dependency_overrides.clear()

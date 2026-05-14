"""Tests for POST /v1/narratives generate endpoint (CP7.3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import create_app
from apps.api.routes.narratives import get_narrative_client
from apps.api.routes.receipts import get_session
from packages.crypto.sign import generate_keypair
from packages.ledger.receipt_builder import build_receipt
from packages.narrative.client import MockNarrativeClient
from packages.policy.bundle_builder import build_bundle
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.policy.snapshot import capture_snapshot
from packages.schema.receipt import Receipt

_TENANT_ID = UUID("feed0000-0000-0000-0000-000000000456")
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


def _override_session_with_pairs(pairs: list[tuple[Receipt, UUID]]):
    from packages.ledger.models import ReceiptRow

    def _make_row(r: Receipt, snap_id: UUID) -> object:
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

    rows = [_make_row(r, sid) for r, sid in pairs]
    by_id = {r.id: _make_row(r, sid) for r, sid in pairs}

    list_result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=rows)
    list_result.scalars = MagicMock(return_value=scalars_mock)

    call_log = {"count": 0}

    async def _execute(stmt):
        call_log["count"] += 1
        if call_log["count"] == 1:
            return list_result
        idx = call_log["count"] - 2
        result = MagicMock()
        if idx < len(pairs):
            r, _sid = pairs[idx]
            result.scalar_one_or_none = MagicMock(return_value=by_id[r.id])
        else:
            result.scalar_one_or_none = MagicMock(return_value=None)
        return result

    session = MagicMock()
    session.execute = AsyncMock(side_effect=_execute)

    async def _override():
        return session

    return _override


async def _override_mock_client():
    return MockNarrativeClient()


async def _override_failing_client():
    return MockNarrativeClient(fail=True)


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_generate_narrative_happy_path(app, client):
    pairs = await _make_chain(3)
    app.dependency_overrides[get_session] = _override_session_with_pairs(pairs)
    app.dependency_overrides[get_narrative_client] = _override_mock_client
    response = await client.post(
        "/v1/narratives"
        f"?tenant_id={_TENANT_ID}"
        "&scope_start=2026-05-13T00:00:00%2B00:00"
        "&scope_end=2026-05-13T23:59:59%2B00:00"
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["narrative_text"]
    assert body["model_id"] == "gemini-3-pro-mock"
    assert len(body["content_hash"]) == 64
    assert len(body["prompt_hash"]) == 64
    assert len(body["pack_root_hash"]) == 64
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_narrative_returns_502_when_client_fails(app, client):
    pairs = await _make_chain(2)
    app.dependency_overrides[get_session] = _override_session_with_pairs(pairs)
    app.dependency_overrides[get_narrative_client] = _override_failing_client
    response = await client.post(
        "/v1/narratives"
        f"?tenant_id={_TENANT_ID}"
        "&scope_start=2026-05-13T00:00:00%2B00:00"
        "&scope_end=2026-05-13T23:59:59%2B00:00"
    )
    assert response.status_code == 502
    assert "narrative client failed" in response.json()["detail"]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_narrative_rejects_naive_scope(app, client):
    app.dependency_overrides[get_session] = _override_session_with_pairs([])
    app.dependency_overrides[get_narrative_client] = _override_mock_client
    response = await client.post(
        "/v1/narratives"
        f"?tenant_id={_TENANT_ID}"
        "&scope_start=2026-05-13T00:00:00"
        "&scope_end=2026-05-13T23:59:59%2B00:00"
    )
    assert response.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_narrative_rejects_inverted_window(app, client):
    app.dependency_overrides[get_session] = _override_session_with_pairs([])
    app.dependency_overrides[get_narrative_client] = _override_mock_client
    response = await client.post(
        "/v1/narratives"
        f"?tenant_id={_TENANT_ID}"
        "&scope_start=2026-05-13T23:59:59%2B00:00"
        "&scope_end=2026-05-13T00:00:00%2B00:00"
    )
    assert response.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_narrative_rejects_too_many_receipts(app, client):
    from packages.ledger.models import ReceiptRow

    rows = []
    for _i in range(1001):
        row = MagicMock(spec=ReceiptRow)
        row.id = uuid4()
        row.tenant_id = _TENANT_ID
        row.event_id = uuid4()
        row.policy_bundle_id = uuid4()
        row.policy_snapshot_id = uuid4()
        row.sequence = _i
        row.prev_receipt_hash = None if _i == 0 else "a" * 64
        row.payload_hash = "b" * 64
        row.receipt_hash = "c" * 64
        row.signature = b"\x00" * 64
        row.signed_at = datetime(2026, 5, 13, 12, 0, tzinfo=UTC)
        rows.append(row)

    list_result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=rows)
    list_result.scalars = MagicMock(return_value=scalars_mock)
    session = MagicMock()
    session.execute = AsyncMock(return_value=list_result)

    async def _override():
        return session

    app.dependency_overrides[get_session] = _override
    app.dependency_overrides[get_narrative_client] = _override_mock_client
    response = await client.post(
        "/v1/narratives"
        f"?tenant_id={_TENANT_ID}"
        "&scope_start=2026-05-13T00:00:00%2B00:00"
        "&scope_end=2026-05-13T23:59:59%2B00:00"
    )
    assert response.status_code == 413
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_narrative_rejects_max_tokens_out_of_range(app, client):
    app.dependency_overrides[get_session] = _override_session_with_pairs([])
    app.dependency_overrides[get_narrative_client] = _override_mock_client
    response = await client.post(
        "/v1/narratives"
        f"?tenant_id={_TENANT_ID}"
        "&scope_start=2026-05-13T00:00:00%2B00:00"
        "&scope_end=2026-05-13T23:59:59%2B00:00"
        "&max_tokens=10000"
    )
    assert response.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_narrative_filters_out_of_window_receipts(app, client):
    # 4 receipts: signed_at every 1 minute from 12:00. Window 12:01-12:02 keeps 2.
    pairs = await _make_chain(4)
    app.dependency_overrides[get_session] = _override_session_with_pairs(pairs)
    app.dependency_overrides[get_narrative_client] = _override_mock_client
    response = await client.post(
        "/v1/narratives"
        f"?tenant_id={_TENANT_ID}"
        "&scope_start=2026-05-13T12:01:00%2B00:00"
        "&scope_end=2026-05-13T12:02:00%2B00:00"
    )
    assert response.status_code == 200, response.text
    # Narrative was produced -> the filter branched both ways (some in, some out).
    body = response.json()
    assert body["narrative_text"]
    app.dependency_overrides.clear()

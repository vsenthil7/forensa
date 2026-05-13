"""Tests for GET /v1/receipts list endpoint.

Strategy: override the get_session dependency with an AsyncMock that returns
a list of pre-built Receipts. No real Postgres needed for unit coverage.
"""

from __future__ import annotations

import base64
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

_TENANT_ID = UUID("55555555-6666-7777-8888-999999999999")
_SAMPLE_CONTENT = {"rules": [{"kind": "x", "decision": "allow"}], "default": "allow"}


async def _make_chain(n: int, tenant_id: UUID = _TENANT_ID) -> list[Receipt]:
    bundle = build_bundle(tenant_id=tenant_id, version="1.0.0", content=_SAMPLE_CONTENT)
    mock = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )
    verdict = await mock.evaluate(tenant_id, {"kind": "x"})
    snap = capture_snapshot(bundle, verdict)
    snap_id = uuid4()
    priv, _ = generate_keypair()
    receipts: list[Receipt] = []
    prev: Receipt | None = None
    for i in range(n):
        r = build_receipt(
            tenant_id=tenant_id,
            event_id=uuid4(),
            event_payload={"step": i},
            policy_snapshot=snap,
            policy_snapshot_id=snap_id,
            prev_receipt=prev,
            tenant_signing_key=priv,
        )
        receipts.append(r)
        prev = r
    return receipts


def _override_session_with(returned_receipts: list[Receipt]):
    """Return a get_session dependency override that yields a mocked AsyncSession."""
    # Build a result mock that scalars().all() returns rows, where each row is a
    # MagicMock(spec=ReceiptRow) with attributes copied from the Receipts above.
    from packages.ledger.models import ReceiptRow

    rows = []
    for r in returned_receipts:
        row = MagicMock(spec=ReceiptRow)
        row.id = r.id
        row.tenant_id = r.tenant_id
        row.event_id = r.event_id
        row.policy_bundle_id = r.policy_bundle_id
        row.sequence = r.sequence
        row.prev_receipt_hash = r.prev_receipt_hash
        row.payload_hash = r.payload_hash
        row.receipt_hash = r.receipt_hash
        row.signature = r.signature
        row.signed_at = r.signed_at
        rows.append(row)

    result_mock = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=rows)
    result_mock.scalars = MagicMock(return_value=scalars_mock)

    session = MagicMock()
    session.execute = AsyncMock(return_value=result_mock)

    async def _override():
        return session

    return _override


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_list_receipts_returns_empty_list_when_no_data(app, client):
    app.dependency_overrides[get_session] = _override_session_with([])
    response = await client.get(f"/v1/receipts?tenant_id={_TENANT_ID}")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["count"] == 0
    assert body["limit"] == 50
    assert body["offset"] == 0
    assert body["tenant_id"] == str(_TENANT_ID)
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_receipts_returns_items_sorted_by_sequence_desc(app, client):
    chain = await _make_chain(3)
    # Mock query returns rows in DESC order (newest first), so reverse the chain
    rows_in_desc = list(reversed(chain))
    app.dependency_overrides[get_session] = _override_session_with(rows_in_desc)
    response = await client.get(f"/v1/receipts?tenant_id={_TENANT_ID}")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 3
    sequences = [item["sequence"] for item in body["items"]]
    assert sequences == [2, 1, 0]
    # signature is base64-encoded
    for item in body["items"]:
        assert item["signature_b64"]
        decoded = base64.b64decode(item["signature_b64"])
        assert len(decoded) == 64
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_receipts_respects_limit_and_offset(app, client):
    chain = await _make_chain(2)
    app.dependency_overrides[get_session] = _override_session_with(chain)
    response = await client.get(f"/v1/receipts?tenant_id={_TENANT_ID}&limit=10&offset=5")
    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 10
    assert body["offset"] == 5
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_receipts_rejects_limit_over_200(app, client):
    app.dependency_overrides[get_session] = _override_session_with([])
    response = await client.get(f"/v1/receipts?tenant_id={_TENANT_ID}&limit=201")
    assert response.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_receipts_rejects_limit_below_one(app, client):
    app.dependency_overrides[get_session] = _override_session_with([])
    response = await client.get(f"/v1/receipts?tenant_id={_TENANT_ID}&limit=0")
    assert response.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_receipts_rejects_negative_offset(app, client):
    app.dependency_overrides[get_session] = _override_session_with([])
    response = await client.get(f"/v1/receipts?tenant_id={_TENANT_ID}&offset=-1")
    assert response.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_receipts_rejects_missing_tenant_id(app, client):
    app.dependency_overrides[get_session] = _override_session_with([])
    response = await client.get("/v1/receipts")
    assert response.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_receipts_rejects_malformed_tenant_id(app, client):
    app.dependency_overrides[get_session] = _override_session_with([])
    response = await client.get("/v1/receipts?tenant_id=not-a-uuid")
    assert response.status_code == 422
    app.dependency_overrides.clear()

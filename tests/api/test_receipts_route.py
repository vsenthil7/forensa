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


# ========== CP5.3 GET /v1/receipts/{receipt_id} ==========


def _override_session_with_single(receipt: Receipt | None, snapshot_id: UUID | None = None):
    """Override that yields a session whose scalar_one_or_none returns one row or None."""
    from packages.ledger.models import ReceiptRow

    if receipt is None:
        row = None
    else:
        row = MagicMock(spec=ReceiptRow)
        row.id = receipt.id
        row.tenant_id = receipt.tenant_id
        row.event_id = receipt.event_id
        row.policy_bundle_id = receipt.policy_bundle_id
        row.policy_snapshot_id = snapshot_id
        row.sequence = receipt.sequence
        row.prev_receipt_hash = receipt.prev_receipt_hash
        row.payload_hash = receipt.payload_hash
        row.receipt_hash = receipt.receipt_hash
        row.signature = receipt.signature
        row.signed_at = receipt.signed_at

    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=row)

    session = MagicMock()
    session.execute = AsyncMock(return_value=result_mock)

    async def _override():
        return session

    return _override


@pytest.mark.asyncio
async def test_get_receipt_returns_404_when_not_found(app, client):
    app.dependency_overrides[get_session] = _override_session_with_single(None)
    response = await client.get(f"/v1/receipts/{uuid4()}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Receipt not found"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_receipt_returns_detail_with_integrity_ok_true_for_untampered(app, client):
    chain = await _make_chain(1)
    receipt = chain[0]
    # Need the snap_id the receipt was actually built with. _make_chain made one
    # internally and didn't return it - we have to reconstruct: any snap_id that
    # makes recompute match. Re-run _make_chain inline to capture the snap_id.
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
    receipt = build_receipt(
        tenant_id=_TENANT_ID,
        event_id=uuid4(),
        event_payload={"step": 0},
        policy_snapshot=snap,
        policy_snapshot_id=snap_id,
        prev_receipt=None,
        tenant_signing_key=priv,
    )
    app.dependency_overrides[get_session] = _override_session_with_single(receipt, snap_id)
    response = await client.get(f"/v1/receipts/{receipt.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(receipt.id)
    assert body["integrity_ok"] is True
    assert body["receipt_hash"] == body["recomputed_receipt_hash"]
    assert body["policy_snapshot_id"] == str(snap_id)
    assert base64.b64decode(body["signature_b64"]) == receipt.signature
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_receipt_returns_integrity_ok_false_when_wrong_snapshot_id(app, client):
    bundle = build_bundle(tenant_id=_TENANT_ID, version="1.0.0", content=_SAMPLE_CONTENT)
    mock = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )
    verdict = await mock.evaluate(_TENANT_ID, {"kind": "x"})
    snap = capture_snapshot(bundle, verdict)
    real_snap_id = uuid4()
    priv, _ = generate_keypair()
    receipt = build_receipt(
        tenant_id=_TENANT_ID,
        event_id=uuid4(),
        event_payload={"step": 0},
        policy_snapshot=snap,
        policy_snapshot_id=real_snap_id,
        prev_receipt=None,
        tenant_signing_key=priv,
    )
    wrong_snap_id = uuid4()  # different from what was bound at build time
    app.dependency_overrides[get_session] = _override_session_with_single(receipt, wrong_snap_id)
    response = await client.get(f"/v1/receipts/{receipt.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["integrity_ok"] is False
    assert body["receipt_hash"] != body["recomputed_receipt_hash"]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_receipt_rejects_malformed_id(app, client):
    app.dependency_overrides[get_session] = _override_session_with_single(None)
    response = await client.get("/v1/receipts/not-a-uuid")
    assert response.status_code == 422
    app.dependency_overrides.clear()


# ========== CP9.12 / NEW-P9.8.4 time-window filter ==========


from datetime import UTC, datetime, timedelta  # noqa: E402


async def _make_chain_with_signed_at(
    n: int, signed_at_base: datetime, tenant_id: UUID = _TENANT_ID
) -> list[Receipt]:
    """Like _make_chain but lets each receipt carry a deterministic signed_at
    so the time-window filter has something predictable to bite on."""
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
        # Override signed_at deterministically.
        r = r.model_copy(update={"signed_at": signed_at_base + timedelta(hours=i)})
        receipts.append(r)
        prev = r
    return receipts


def _override_session_honouring_signed_at(returned_receipts: list[Receipt]):
    """Override that inspects the compiled SQL and filters rows according to
    the signed_at >= / <= clauses actually present in the query.

    Reads the SQL string and the bound params to determine the lower/upper
    bounds independently - same pattern as test_evidence_route.py but smarter
    about distinguishing >= from <= clauses (the evidence-route uses an
    inclusive BETWEEN-style window where the simple ``min/max`` heuristic
    works; this CP9.12 fixture sees queries with EITHER clause OR BOTH so we
    have to read the SQL text).

    If neither clause appears, all rows are returned.
    """
    from packages.ledger.models import ReceiptRow

    def _make_row(r: Receipt) -> object:
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
        return row

    all_rows = [(r, _make_row(r)) for r in returned_receipts]

    async def _execute(stmt):
        try:
            compiled = stmt.compile()
            params = compiled.params
            sql = str(compiled)
        except Exception:  # pragma: no cover - defensive
            params = {}
            sql = ""
        datetimes = [(k, v) for k, v in params.items() if isinstance(v, datetime)]
        # Map each bound datetime to whether it's the lower or upper bound
        # by checking which clause references its param name.
        lower_bound: datetime | None = None
        upper_bound: datetime | None = None
        for name, dt in datetimes:
            placeholder = f":{name}"
            # Look at the snippet of SQL just before the placeholder.
            idx = sql.find(placeholder)
            if idx < 0:
                continue
            preceding = sql[:idx]
            # The clause is one of: signed_at >= :name  /  signed_at <= :name
            if ">=" in preceding.rsplit("signed_at", 1)[-1]:
                lower_bound = dt
            elif "<=" in preceding.rsplit("signed_at", 1)[-1]:
                upper_bound = dt

        filtered = []
        for r, row in all_rows:
            if lower_bound is not None and r.signed_at < lower_bound:
                continue
            if upper_bound is not None and r.signed_at > upper_bound:
                continue
            filtered.append(row)

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


@pytest.mark.asyncio
async def test_list_receipts_signed_after_only_filters_lower_bound(app, client):
    """Pass only signed_after - receipts older than the bound are excluded."""
    base = datetime(2026, 5, 13, 12, 0, tzinfo=UTC)
    chain = await _make_chain_with_signed_at(5, base)
    # chain[i].signed_at == base + i hours
    app.dependency_overrides[get_session] = _override_session_honouring_signed_at(chain)
    after = (base + timedelta(hours=2)).isoformat().replace("+00:00", "%2B00:00")
    response = await client.get(f"/v1/receipts?tenant_id={_TENANT_ID}&signed_after={after}")
    assert response.status_code == 200
    body = response.json()
    # Only chain[2], chain[3], chain[4] survive
    sequences = sorted(item["sequence"] for item in body["items"])
    assert sequences == [2, 3, 4]
    # Echo of the bound
    assert body["signed_after"] is not None
    assert body["signed_before"] is None
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_receipts_signed_before_only_filters_upper_bound(app, client):
    base = datetime(2026, 5, 13, 12, 0, tzinfo=UTC)
    chain = await _make_chain_with_signed_at(5, base)
    app.dependency_overrides[get_session] = _override_session_honouring_signed_at(chain)
    before = (base + timedelta(hours=2)).isoformat().replace("+00:00", "%2B00:00")
    response = await client.get(f"/v1/receipts?tenant_id={_TENANT_ID}&signed_before={before}")
    assert response.status_code == 200
    body = response.json()
    sequences = sorted(item["sequence"] for item in body["items"])
    # chain[0], chain[1], chain[2] (inclusive upper bound)
    assert sequences == [0, 1, 2]
    assert body["signed_after"] is None
    assert body["signed_before"] is not None
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_receipts_signed_after_and_before_window(app, client):
    base = datetime(2026, 5, 13, 12, 0, tzinfo=UTC)
    chain = await _make_chain_with_signed_at(5, base)
    app.dependency_overrides[get_session] = _override_session_honouring_signed_at(chain)
    after = (base + timedelta(hours=1)).isoformat().replace("+00:00", "%2B00:00")
    before = (base + timedelta(hours=3)).isoformat().replace("+00:00", "%2B00:00")
    response = await client.get(
        f"/v1/receipts?tenant_id={_TENANT_ID}&signed_after={after}&signed_before={before}"
    )
    assert response.status_code == 200
    body = response.json()
    sequences = sorted(item["sequence"] for item in body["items"])
    # chain[1], chain[2], chain[3] (both bounds inclusive)
    assert sequences == [1, 2, 3]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_receipts_rejects_naive_signed_after(app, client):
    app.dependency_overrides[get_session] = _override_session_honouring_signed_at([])
    response = await client.get(
        f"/v1/receipts?tenant_id={_TENANT_ID}&signed_after=2026-05-13T12:00:00"
    )
    assert response.status_code == 422
    assert "timezone-aware" in response.json()["detail"]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_receipts_rejects_naive_signed_before(app, client):
    app.dependency_overrides[get_session] = _override_session_honouring_signed_at([])
    response = await client.get(
        f"/v1/receipts?tenant_id={_TENANT_ID}&signed_before=2026-05-13T12:00:00"
    )
    assert response.status_code == 422
    assert "timezone-aware" in response.json()["detail"]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_receipts_rejects_inverted_window(app, client):
    app.dependency_overrides[get_session] = _override_session_honouring_signed_at([])
    after = "2026-05-13T18:00:00%2B00:00"
    before = "2026-05-13T12:00:00%2B00:00"  # before < after
    response = await client.get(
        f"/v1/receipts?tenant_id={_TENANT_ID}&signed_after={after}&signed_before={before}"
    )
    assert response.status_code == 422
    assert "must be <=" in response.json()["detail"]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_receipts_time_window_combines_with_cursor_pagination(app, client):
    """signed_after/before and before_sequence cursor compose - the route
    threads both through to ``list_receipts_for_tenant_cursor``."""
    base = datetime(2026, 5, 13, 12, 0, tzinfo=UTC)
    chain = await _make_chain_with_signed_at(5, base)
    app.dependency_overrides[get_session] = _override_session_honouring_signed_at(chain)
    after = base.isoformat().replace("+00:00", "%2B00:00")
    before = (base + timedelta(hours=10)).isoformat().replace("+00:00", "%2B00:00")
    response = await client.get(
        f"/v1/receipts?tenant_id={_TENANT_ID}"
        f"&signed_after={after}&signed_before={before}&before_sequence=10"
    )
    assert response.status_code == 200
    body = response.json()
    # Whole window included; before_sequence=10 lets all 5 through.
    assert body["count"] == 5
    # Cursor mode echoed: offset=0, before_sequence=10, time window echoed.
    assert body["offset"] == 0
    assert body["before_sequence"] == 10
    assert body["signed_after"] is not None
    assert body["signed_before"] is not None
    app.dependency_overrides.clear()

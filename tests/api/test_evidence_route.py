"""Tests for GET /v1/evidence-packs export endpoint.

Strategy: override get_session with a mock that returns a controlled list of
receipts. Uses real build_evidence_pack and build_receipt to produce
cryptographically valid receipts so the root_hash recompute path works.
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
from packages.policy.bundle_builder import build_bundle
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.policy.snapshot import capture_snapshot
from packages.schema.receipt import Receipt
from tests.api._auth_helpers import install_principal_override

_TENANT_ID = UUID("77777777-8888-9999-aaaa-bbbbbbbbbbbb")
_AGENT_ID = UUID("88888888-9999-aaaa-bbbb-cccccccccccc")
_SAMPLE_CONTENT = {"rules": [{"kind": "x", "decision": "allow"}], "default": "allow"}


async def _make_chain(
    n: int, tenant_id: UUID = _TENANT_ID, signed_at_base: datetime | None = None
) -> list[tuple[Receipt, UUID]]:
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
    pairs: list[tuple[Receipt, UUID]] = []
    prev: Receipt | None = None
    base = signed_at_base or datetime(2026, 5, 13, 12, 0, tzinfo=UTC)
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
        # Override signed_at deterministically via model_copy
        r = r.model_copy(update={"signed_at": base + timedelta(minutes=i)})
        pairs.append((r, snap_id))
        prev = r
    return pairs


def _override_session_with_pairs(pairs: list[tuple[Receipt, UUID]]):
    """Override that handles the single execute() call from the route.

    CP9.7: the route now calls ``list_receipts_with_snapshot_for_tenant`` which
    does a single SELECT with the (tenant_id, signed_at BETWEEN, ORDER BY
    sequence ASC) WHERE clause. The mock returns the rows whose ``signed_at``
    falls inside the query's window so the test stays honest about what the
    real DB would return. The window is extracted from the compiled
    statement's bound parameters.
    """
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
        row.agent_signature = None  # CP9.18: backwards-compat (pre-migration-0006)
        row.signed_at = r.signed_at
        return row

    all_rows = [(r, _make_row(r, sid)) for r, sid in pairs]

    async def _execute(stmt):
        # Extract the signed_at window from the SELECT's compiled parameters
        # so the mock honours the WHERE clause the real DB would apply.
        try:
            compiled = stmt.compile()
            params = compiled.params
        except Exception:  # pragma: no cover - defensive
            params = {}
        start = None
        end = None
        for v in params.values():
            if isinstance(v, datetime):
                if start is None or v < start:
                    start = v
                if end is None or v > end:
                    end = v
        if start is not None and end is not None:
            in_window = [row for r, row in all_rows if start <= r.signed_at <= end]
        else:
            in_window = [row for _r, row in all_rows]
        scalars_mock = MagicMock()
        scalars_mock.all = MagicMock(return_value=in_window)
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
async def test_export_evidence_pack_happy_path_returns_jsonld(app, client):
    pairs = await _make_chain(3)
    app.dependency_overrides[get_session] = _override_session_with_pairs(pairs)
    response = await client.get(
        "/v1/evidence-packs"
        f"?tenant_id={_TENANT_ID}"
        "&scope_start=2026-05-13T00:00:00%2B00:00"
        "&scope_end=2026-05-13T23:59:59%2B00:00"
    )
    assert response.status_code == 200, response.text
    body = response.json()
    # Pydantic serialises Field(alias="@context") -> @context in by_alias mode
    # but default model_dump uses field name; accept either.
    assert "root_hash" in body
    assert "receipts" in body
    assert "activities" in body
    assert len(body["receipts"]) == 3
    assert len(body["activities"]) == 3
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_export_evidence_pack_empty_window_returns_zero_receipts(app, client):
    pairs = await _make_chain(2, signed_at_base=datetime(2026, 1, 1, tzinfo=UTC))
    app.dependency_overrides[get_session] = _override_session_with_pairs(pairs)
    # Window does not overlap with signed_at base
    response = await client.get(
        "/v1/evidence-packs"
        f"?tenant_id={_TENANT_ID}"
        "&scope_start=2026-05-13T00:00:00%2B00:00"
        "&scope_end=2026-05-13T23:59:59%2B00:00"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["receipts"] == []
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_export_evidence_pack_rejects_naive_scope_start(app, client):
    app.dependency_overrides[get_session] = _override_session_with_pairs([])
    response = await client.get(
        "/v1/evidence-packs"
        f"?tenant_id={_TENANT_ID}"
        "&scope_start=2026-05-13T00:00:00"  # no tz
        "&scope_end=2026-05-13T23:59:59%2B00:00"
    )
    assert response.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_export_evidence_pack_rejects_inverted_window(app, client):
    app.dependency_overrides[get_session] = _override_session_with_pairs([])
    response = await client.get(
        "/v1/evidence-packs"
        f"?tenant_id={_TENANT_ID}"
        "&scope_start=2026-05-13T23:59:59%2B00:00"
        "&scope_end=2026-05-13T00:00:00%2B00:00"
    )
    assert response.status_code == 422
    body = response.json()
    assert "scope_end" in body["detail"]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_export_evidence_pack_rejects_too_many_receipts(app, client):
    # Build a fake list of 1001 row stubs without doing 1001 real receipts.
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
        row.agent_signature = None  # CP9.18: backwards-compat
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
    response = await client.get(
        "/v1/evidence-packs"
        f"?tenant_id={_TENANT_ID}"
        "&scope_start=2026-05-13T00:00:00%2B00:00"
        "&scope_end=2026-05-13T23:59:59%2B00:00"
    )
    assert response.status_code == 413
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_export_evidence_pack_rejects_missing_tenant_id(app, client):
    app.dependency_overrides[get_session] = _override_session_with_pairs([])
    response = await client.get(
        "/v1/evidence-packs"
        "?scope_start=2026-05-13T00:00:00%2B00:00"
        "&scope_end=2026-05-13T23:59:59%2B00:00"
    )
    assert response.status_code == 422
    app.dependency_overrides.clear()

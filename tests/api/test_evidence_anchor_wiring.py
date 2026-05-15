"""Tests for CP9.24 - anchor wiring in GET /v1/evidence-packs.

Positive-path coverage: the route's _latest_anchor_in_window helper looks
up a TimestampAnchorRow inside the scope window and passes it to
build_evidence_pack. When such a row exists, the returned pack carries a
non-None ``anchor`` field bound into root_hash.

The mocked session is more elaborate than test_evidence_route.py's: the
receipts query returns ReceiptRow stubs; the anchor query returns a
TimestampAnchorRow stub. SQL discrimination is by 'timestamp_anchors'
table name in the compiled statement.
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

_TENANT = UUID("77777777-8888-9999-aaaa-bbbbbbbbbbbb")
_AGENT = UUID("88888888-9999-aaaa-bbbb-cccccccccccc")
_CONTENT = {"rules": [{"kind": "x", "decision": "allow"}], "default": "allow"}


async def _make_chain(n: int) -> list[tuple[Receipt, UUID]]:
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
    base = datetime(2026, 5, 13, 12, 0, tzinfo=UTC)
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
        r = r.model_copy(update={"signed_at": base + timedelta(minutes=i)})
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


def _make_anchor_row(*, status: str = "anchored") -> object:
    """Build a TimestampAnchorRow-shaped mock that from_anchor_row accepts."""
    from packages.ledger.models import TimestampAnchorRow

    row = MagicMock(spec=TimestampAnchorRow)
    row.id = uuid4()
    row.tenant_id = _TENANT
    row.anchor_date = datetime(2026, 5, 13, tzinfo=UTC)
    row.status = status
    row.root_hash = ("a" * 64) if status == "anchored" else None
    row.tsa_identifier = "mock-tsa"
    row.tsr_bytes = b"\x00\x01\x02" if status == "anchored" else None
    row.tsa_signature = (b"\xff" * 32) if status == "anchored" else None
    row.timestamped_at = datetime(2026, 5, 13, 12, 0, tzinfo=UTC) if status == "anchored" else None
    row.anchored_at = datetime(2026, 5, 13, 12, 5, tzinfo=UTC)
    return row


def _override_session_with_anchor(
    receipts_pairs: list[tuple[Receipt, UUID]], anchor_row: object | None
):
    """Mock session that returns receipts for the receipts query AND the
    given anchor_row (or None) for the anchor query."""
    receipt_rows = [_make_receipt_row(r, sid) for r, sid in receipts_pairs]

    async def _execute(stmt):
        sql_str = str(stmt).lower()
        if "timestamp_anchors" in sql_str:
            # Anchor query path.
            result = MagicMock()
            result.scalar_one_or_none = MagicMock(return_value=anchor_row)
            return result
        # Receipts query path.
        scalars_mock = MagicMock()
        scalars_mock.all = MagicMock(return_value=receipt_rows)
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


_QS = (
    f"?tenant_id={_TENANT}"
    "&scope_start=2026-05-13T00:00:00%2B00:00"
    "&scope_end=2026-05-13T23:59:59%2B00:00"
)


@pytest.mark.asyncio
async def test_jsonld_pack_surfaces_anchored_anchor_when_row_exists(app, client) -> None:
    pairs = await _make_chain(2)
    anchor_row = _make_anchor_row(status="anchored")
    app.dependency_overrides[get_session] = _override_session_with_anchor(pairs, anchor_row)
    response = await client.get(f"/v1/evidence-packs{_QS}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["anchor"] is not None
    anchor = body["anchor"]
    assert anchor["status"] == "anchored"
    assert anchor["root_hash"] == "a" * 64
    assert anchor["tsa_identifier"] == "mock-tsa"
    assert anchor["tsr_bytes_b64"] is not None
    assert anchor["tsa_signature_b64"] is not None
    assert anchor["timestamped_at"] is not None
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_jsonld_pack_surfaces_deferred_anchor_when_row_is_tombstone(app, client) -> None:
    pairs = await _make_chain(1)
    anchor_row = _make_anchor_row(status="deferred")
    app.dependency_overrides[get_session] = _override_session_with_anchor(pairs, anchor_row)
    response = await client.get(f"/v1/evidence-packs{_QS}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["anchor"] is not None
    anchor = body["anchor"]
    assert anchor["status"] == "deferred"
    assert anchor["root_hash"] is None
    assert anchor["tsr_bytes_b64"] is None
    assert anchor["tsa_signature_b64"] is None
    assert anchor["timestamped_at"] is None
    # Even a deferred anchor must be bound into root_hash so subsequent
    # tampering with the anchor invalidates the pack.
    assert len(body["root_hash"]) == 64
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_jsonld_pack_has_null_anchor_when_no_row_in_window(app, client) -> None:
    pairs = await _make_chain(2)
    # Anchor query returns None (no row for this window).
    app.dependency_overrides[get_session] = _override_session_with_anchor(pairs, None)
    response = await client.get(f"/v1/evidence-packs{_QS}")
    assert response.status_code == 200
    body = response.json()
    assert body["anchor"] is None
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_pdf_pack_with_anchored_anchor_still_renders(app, client) -> None:
    pairs = await _make_chain(2)
    anchor_row = _make_anchor_row(status="anchored")
    app.dependency_overrides[get_session] = _override_session_with_anchor(pairs, anchor_row)
    response = await client.get(
        f"/v1/evidence-packs{_QS}",
        headers={"Accept": "application/pdf"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
    # X-Forensa-Root-Hash is the JSON-LD pack's root_hash which now includes
    # the anchor in its bind. The anchor-bound root_hash differs from the
    # would-be-anchorless root_hash for the same receipts.
    root_hash = response.headers["x-forensa-root-hash"]
    assert len(root_hash) == 64
    app.dependency_overrides.clear()

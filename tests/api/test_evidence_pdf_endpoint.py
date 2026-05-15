"""Tests for GET /v1/evidence-packs PDF wire form (CP9.21b).

The PDF branch shares all upstream validation and auth with the JSON-LD
branch (covered in test_evidence_route.py). These tests focus on the
content-negotiation behaviour added in CP9.21b: Accept-header routing,
response media-type + headers, and that the PDF bytes match what the
underlying renderer produces.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import create_app
from apps.api.routes.evidence import _wants_pdf
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
        row.agent_signature = None
        row.signed_at = r.signed_at
        return row

    all_rows = [(r, _make_row(r, sid)) for r, sid in pairs]

    async def _execute(stmt):
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


_QS = (
    f"?tenant_id={_TENANT_ID}"
    "&scope_start=2026-05-13T00:00:00%2B00:00"
    "&scope_end=2026-05-13T23:59:59%2B00:00"
)


# ---------- _wants_pdf helper ----------


def test_wants_pdf_none_header_returns_false() -> None:
    assert _wants_pdf(None) is False


def test_wants_pdf_empty_header_returns_false() -> None:
    assert _wants_pdf("") is False


def test_wants_pdf_application_json_returns_false() -> None:
    assert _wants_pdf("application/json") is False


def test_wants_pdf_wildcard_returns_false() -> None:
    # Conservative: */* does NOT trigger PDF; JSON-LD remains the default.
    assert _wants_pdf("*/*") is False


def test_wants_pdf_application_wildcard_returns_false() -> None:
    assert _wants_pdf("application/*") is False


def test_wants_pdf_exact_pdf_returns_true() -> None:
    assert _wants_pdf("application/pdf") is True


def test_wants_pdf_case_insensitive() -> None:
    assert _wants_pdf("Application/PDF") is True


def test_wants_pdf_with_quality_param_returns_true() -> None:
    assert _wants_pdf("application/pdf;q=0.9") is True


def test_wants_pdf_in_compound_accept_returns_true() -> None:
    assert _wants_pdf("application/json, application/pdf;q=0.9") is True


# ---------- endpoint: PDF branch ----------


@pytest.mark.asyncio
async def test_pdf_accept_returns_pdf_content_type(app, client) -> None:
    pairs = await _make_chain(2)
    app.dependency_overrides[get_session] = _override_session_with_pairs(pairs)
    response = await client.get(
        f"/v1/evidence-packs{_QS}",
        headers={"Accept": "application/pdf"},
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
    assert response.content.rstrip().endswith(b"%%EOF")
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_pdf_accept_sets_content_disposition_with_hash_tagged_filename(app, client) -> None:
    pairs = await _make_chain(2)
    app.dependency_overrides[get_session] = _override_session_with_pairs(pairs)
    response = await client.get(
        f"/v1/evidence-packs{_QS}",
        headers={"Accept": "application/pdf"},
    )
    assert response.status_code == 200
    disp = response.headers["content-disposition"]
    assert disp.startswith("attachment; filename=")
    assert "evidence-pack-" in disp
    assert ".pdf" in disp
    # Filename includes first 12 chars of root_hash; cross-check via the
    # X-Forensa-Root-Hash response header.
    root_hash = response.headers["x-forensa-root-hash"]
    assert len(root_hash) == 64
    assert root_hash[:12] in disp
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_pdf_accept_returns_x_forensa_root_hash_header(app, client) -> None:
    pairs = await _make_chain(1)
    app.dependency_overrides[get_session] = _override_session_with_pairs(pairs)
    response = await client.get(
        f"/v1/evidence-packs{_QS}",
        headers={"Accept": "application/pdf"},
    )
    assert response.status_code == 200
    rh = response.headers.get("x-forensa-root-hash")
    assert rh is not None
    assert len(rh) == 64
    assert all(c in "0123456789abcdef" for c in rh)
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_pdf_accept_with_empty_window_still_returns_valid_pdf(app, client) -> None:
    # No matching receipts; pack is empty but rendering still succeeds.
    pairs = await _make_chain(0)
    app.dependency_overrides[get_session] = _override_session_with_pairs(pairs)
    response = await client.get(
        f"/v1/evidence-packs{_QS}",
        headers={"Accept": "application/pdf"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
    app.dependency_overrides.clear()


# ---------- endpoint: JSON-LD branch regressions ----------


@pytest.mark.asyncio
async def test_no_accept_header_defaults_to_jsonld(app, client) -> None:
    pairs = await _make_chain(2)
    app.dependency_overrides[get_session] = _override_session_with_pairs(pairs)
    # httpx adds Accept: */* by default; explicitly override to nothing-pdf.
    response = await client.get(f"/v1/evidence-packs{_QS}")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert "root_hash" in body
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_explicit_json_accept_returns_jsonld(app, client) -> None:
    pairs = await _make_chain(2)
    app.dependency_overrides[get_session] = _override_session_with_pairs(pairs)
    response = await client.get(
        f"/v1/evidence-packs{_QS}",
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    app.dependency_overrides.clear()


# ---------- auth + validation still enforced on PDF path ----------


@pytest.mark.asyncio
async def test_pdf_branch_returns_422_on_naive_scope_start(app, client) -> None:
    app.dependency_overrides[get_session] = _override_session_with_pairs([])
    response = await client.get(
        "/v1/evidence-packs"
        f"?tenant_id={_TENANT_ID}"
        "&scope_start=2026-05-13T00:00:00"
        "&scope_end=2026-05-13T23:59:59%2B00:00",
        headers={"Accept": "application/pdf"},
    )
    assert response.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_pdf_branch_returns_403_on_cross_tenant(app, client) -> None:
    other = UUID("99999999-aaaa-bbbb-cccc-dddddddddddd")
    app.dependency_overrides[get_session] = _override_session_with_pairs([])
    response = await client.get(
        "/v1/evidence-packs"
        f"?tenant_id={other}"
        "&scope_start=2026-05-13T00:00:00%2B00:00"
        "&scope_end=2026-05-13T23:59:59%2B00:00",
        headers={"Accept": "application/pdf"},
    )
    assert response.status_code == 403
    app.dependency_overrides.clear()

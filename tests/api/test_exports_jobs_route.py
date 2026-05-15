"""Tests for POST /v1/exports/ma-diligence/jobs + GET status + list (CP9.45 / IP #8).

Route half of NEW-P12.X.ma-export-async-job. The CP9.44 runner is
mocked out at the asyncio.create_task layer so these unit tests don't
need a real DB or a real event loop scheduler. PG integration tests
in tests/integration/test_exports_jobs_pg.py exercise the full
POST -> runner -> GET-status round trip against real Postgres.

Coverage:
  - POST 202 happy path: row inserted, runner scheduled, response shape
  - POST 403 cross-tenant: body.tenant_id != principal.tenant_id
  - POST 422 naive scope_start / scope_end
  - POST 422 inverted window (scope_end < scope_start)
  - POST 422 garbage encrypt_for_pubkey_b64
  - POST passes encrypt + sign metadata through to the repo
  - GET 200 happy path: tenant-scoped fetch
  - GET 404 not found
  - GET 404 cross-tenant (oracle-safe: same surface as missing)
  - LIST 200 happy path: items + count
  - LIST 200 empty
  - LIST tenant scoping is implicit (no tenant_id query param)
  - get_sessionmaker default stub raises NotImplementedError
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import create_app
from apps.api.routes.exports import get_sessionmaker
from apps.api.routes.receipts import get_session
from tests.api._auth_helpers import install_principal_override

_TENANT_ID = UUID("33333333-4444-5555-6666-777777777777")
_AGENT_ID = UUID("44444444-5555-6666-7777-888888888888")
_OTHER_TENANT = UUID("99999999-aaaa-bbbb-cccc-dddddddddddd")


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


# ---------- helpers ----------


def _make_job_row(
    *,
    tenant_id: UUID = _TENANT_ID,
    status: str = "pending",
    scope_start: datetime | None = None,
    scope_end: datetime | None = None,
    result_export: dict | None = None,
    result_error: str | None = None,
):
    """Build a MagicMock that satisfies MaExportJobStatusResponse.from_row."""
    row = MagicMock()
    row.id = uuid4()
    row.tenant_id = tenant_id
    row.status = status
    row.scope_start = scope_start or datetime(2026, 1, 1, tzinfo=UTC)
    row.scope_end = scope_end or datetime(2026, 5, 1, tzinfo=UTC)
    row.requested_at = datetime(2026, 5, 15, tzinfo=UTC)
    row.started_at = datetime(2026, 5, 15, tzinfo=UTC) if status != "pending" else None
    row.completed_at = (
        datetime(2026, 5, 15, tzinfo=UTC) if status in ("completed", "failed") else None
    )
    row.result_export = result_export
    row.result_error = result_error
    return row


# ---------- POST 202 happy path ----------


@pytest.mark.asyncio
async def test_post_creates_job_returns_202_and_job_id(app, client, monkeypatch) -> None:
    """Happy path: POST returns 202 + job_id; create_ma_export_job invoked."""
    create_calls: list[dict] = []

    async def _fake_create(
        session,
        *,
        tenant_id,
        scope_start,
        scope_end,
        encrypt_for_pubkey_b64=None,
        platform_sign_key_id=None,
        requested_by_agent_id=None,
    ):
        fake_id = uuid4()
        create_calls.append(
            {
                "tenant_id": tenant_id,
                "scope_start": scope_start,
                "scope_end": scope_end,
                "encrypt_for_pubkey_b64": encrypt_for_pubkey_b64,
                "platform_sign_key_id": platform_sign_key_id,
                "requested_by_agent_id": requested_by_agent_id,
                "returned_id": fake_id,
            }
        )
        return fake_id

    schedule_calls: list[dict] = []

    def _fake_create_task(coro, *, name=None):
        # Close the coroutine so it doesn't warn about being unawaited.
        coro.close()
        schedule_calls.append({"name": name})
        return MagicMock()

    from apps.api.routes import exports as exports_mod

    monkeypatch.setattr(exports_mod, "create_ma_export_job", _fake_create)
    monkeypatch.setattr(exports_mod.asyncio, "create_task", _fake_create_task)

    session = MagicMock()
    session.commit = AsyncMock()

    async def _session_override():
        return session

    async def _sm_override():
        return MagicMock()

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_sessionmaker] = _sm_override

    body = {
        "tenant_id": str(_TENANT_ID),
        "scope_start": "2026-01-01T00:00:00+00:00",
        "scope_end": "2026-05-01T00:00:00+00:00",
    }
    response = await client.post("/v1/exports/ma-diligence/jobs", json=body)
    assert response.status_code == 202, response.text
    resp_body = response.json()
    assert "job_id" in resp_body
    assert resp_body["status"] == "pending"
    expected_job_id = create_calls[0]["returned_id"]
    assert resp_body["job_id"] == str(expected_job_id)
    assert resp_body["poll_url"] == f"/v1/exports/ma-diligence/jobs/{expected_job_id}"
    # The repo + scheduler were both invoked.
    assert len(create_calls) == 1
    assert create_calls[0]["tenant_id"] == _TENANT_ID
    assert create_calls[0]["requested_by_agent_id"] == _AGENT_ID
    assert len(schedule_calls) == 1
    assert str(expected_job_id) in schedule_calls[0]["name"]
    # The session was committed (necessary so the runner sees the row).
    session.commit.assert_awaited_once()
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_post_passes_encryption_and_signing_metadata(app, client, monkeypatch) -> None:
    """Encryption + signing params on the request body land on the row."""
    create_calls: list[dict] = []

    async def _fake_create(session, **kwargs):
        create_calls.append(kwargs)
        return uuid4()

    def _fake_create_task(coro, *, name=None):
        coro.close()
        return MagicMock()

    from apps.api.routes import exports as exports_mod

    monkeypatch.setattr(exports_mod, "create_ma_export_job", _fake_create)
    monkeypatch.setattr(exports_mod.asyncio, "create_task", _fake_create_task)

    session = MagicMock()
    session.commit = AsyncMock()

    async def _session_override():
        return session

    async def _sm_override():
        return MagicMock()

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_sessionmaker] = _sm_override

    # 32-byte X25519 pubkey, url-safe-b64 (43 chars, no padding).
    pubkey_b64 = "AAAA" + "B" * 39
    body = {
        "tenant_id": str(_TENANT_ID),
        "scope_start": "2026-01-01T00:00:00+00:00",
        "scope_end": "2026-05-01T00:00:00+00:00",
        "encrypt_for_pubkey_b64": pubkey_b64,
        "platform_sign_key_id": "forensa-platform-key-v1",
    }
    response = await client.post("/v1/exports/ma-diligence/jobs", json=body)
    assert response.status_code == 202, response.text
    assert create_calls[0]["encrypt_for_pubkey_b64"] == pubkey_b64
    assert create_calls[0]["platform_sign_key_id"] == "forensa-platform-key-v1"
    app.dependency_overrides.clear()


# ---------- POST 403 cross-tenant ----------


@pytest.mark.asyncio
async def test_post_blocks_cross_tenant_with_403(app, client) -> None:
    session = MagicMock()

    async def _session_override():
        return session

    async def _sm_override():
        return MagicMock()

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_sessionmaker] = _sm_override

    body = {
        "tenant_id": str(_OTHER_TENANT),  # NOT principal.tenant_id
        "scope_start": "2026-01-01T00:00:00+00:00",
        "scope_end": "2026-05-01T00:00:00+00:00",
    }
    response = await client.post("/v1/exports/ma-diligence/jobs", json=body)
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "tenant_mismatch"
    app.dependency_overrides.clear()


# ---------- POST 422 validation ----------


@pytest.mark.asyncio
async def test_post_422_when_scope_start_naive(app, client) -> None:
    session = MagicMock()

    async def _session_override():
        return session

    async def _sm_override():
        return MagicMock()

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_sessionmaker] = _sm_override

    body = {
        "tenant_id": str(_TENANT_ID),
        "scope_start": "2026-01-01T00:00:00",  # NAIVE - no tzinfo
        "scope_end": "2026-05-01T00:00:00+00:00",
    }
    response = await client.post("/v1/exports/ma-diligence/jobs", json=body)
    assert response.status_code == 422
    assert "timezone-aware" in str(response.json()["detail"])
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_post_422_when_scope_end_naive(app, client) -> None:
    session = MagicMock()

    async def _session_override():
        return session

    async def _sm_override():
        return MagicMock()

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_sessionmaker] = _sm_override

    body = {
        "tenant_id": str(_TENANT_ID),
        "scope_start": "2026-01-01T00:00:00+00:00",
        "scope_end": "2026-05-01T00:00:00",  # NAIVE
    }
    response = await client.post("/v1/exports/ma-diligence/jobs", json=body)
    assert response.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_post_422_when_scope_inverted(app, client) -> None:
    session = MagicMock()

    async def _session_override():
        return session

    async def _sm_override():
        return MagicMock()

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_sessionmaker] = _sm_override

    body = {
        "tenant_id": str(_TENANT_ID),
        "scope_start": "2026-05-01T00:00:00+00:00",
        "scope_end": "2026-01-01T00:00:00+00:00",  # before start
    }
    response = await client.post("/v1/exports/ma-diligence/jobs", json=body)
    assert response.status_code == 422
    assert "scope_end" in str(response.json()["detail"])
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_post_422_when_pubkey_not_base64(app, client) -> None:
    session = MagicMock()

    async def _session_override():
        return session

    async def _sm_override():
        return MagicMock()

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_sessionmaker] = _sm_override

    body = {
        "tenant_id": str(_TENANT_ID),
        "scope_start": "2026-01-01T00:00:00+00:00",
        "scope_end": "2026-05-01T00:00:00+00:00",
        # Non-ASCII -> base64 decoder rejects.
        "encrypt_for_pubkey_b64": "AAAA" + chr(255),
    }
    response = await client.post("/v1/exports/ma-diligence/jobs", json=body)
    assert response.status_code == 422
    assert "base64" in str(response.json()["detail"])
    app.dependency_overrides.clear()


# ---------- GET status ----------


@pytest.mark.asyncio
async def test_get_status_returns_pending_row(app, client, monkeypatch) -> None:
    row = _make_job_row(status="pending")

    captured: dict = {}

    async def _fake_get(session, job_id, *, tenant_id=None):
        captured["job_id"] = job_id
        captured["tenant_id"] = tenant_id
        return row

    from apps.api.routes import exports as exports_mod

    monkeypatch.setattr(exports_mod, "get_ma_export_job_by_id", _fake_get)

    session = MagicMock()

    async def _session_override():
        return session

    app.dependency_overrides[get_session] = _session_override

    response = await client.get(f"/v1/exports/ma-diligence/jobs/{row.id}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["job_id"] == str(row.id)
    assert body["tenant_id"] == str(_TENANT_ID)
    assert body["status"] == "pending"
    assert body["result_export"] is None
    assert body["result_error"] is None
    # Tenant-scoped fetch.
    assert captured["tenant_id"] == _TENANT_ID
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_status_returns_completed_row_with_result_export(
    app, client, monkeypatch
) -> None:
    result = {
        "@type": "forensa:MaDiligenceExport",
        "ma_root_hash": "a" * 64,
    }
    row = _make_job_row(status="completed", result_export=result)

    async def _fake_get(session, job_id, *, tenant_id=None):
        return row

    from apps.api.routes import exports as exports_mod

    monkeypatch.setattr(exports_mod, "get_ma_export_job_by_id", _fake_get)

    async def _session_override():
        return MagicMock()

    app.dependency_overrides[get_session] = _session_override

    response = await client.get(f"/v1/exports/ma-diligence/jobs/{row.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["result_export"] == result
    assert body["started_at"] is not None
    assert body["completed_at"] is not None
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_status_returns_failed_row_with_result_error(app, client, monkeypatch) -> None:
    row = _make_job_row(status="failed", result_error="MaExportError: bundle too big")

    async def _fake_get(session, job_id, *, tenant_id=None):
        return row

    from apps.api.routes import exports as exports_mod

    monkeypatch.setattr(exports_mod, "get_ma_export_job_by_id", _fake_get)

    async def _session_override():
        return MagicMock()

    app.dependency_overrides[get_session] = _session_override

    response = await client.get(f"/v1/exports/ma-diligence/jobs/{row.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["result_error"] == "MaExportError: bundle too big"
    assert body["result_export"] is None
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_status_404_when_job_not_found(app, client, monkeypatch) -> None:
    async def _fake_get(session, job_id, *, tenant_id=None):
        return None  # row missing

    from apps.api.routes import exports as exports_mod

    monkeypatch.setattr(exports_mod, "get_ma_export_job_by_id", _fake_get)

    async def _session_override():
        return MagicMock()

    app.dependency_overrides[get_session] = _session_override

    response = await client.get(f"/v1/exports/ma-diligence/jobs/{uuid4()}")
    assert response.status_code == 404
    assert response.json()["detail"] == "job not found"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_status_404_when_cross_tenant_oracle_safe(app, client, monkeypatch) -> None:
    """A cross-tenant probe gets 404, not 403, so attackers can't enumerate
    which job_ids exist for other tenants."""
    captured: dict = {}

    async def _fake_get(session, job_id, *, tenant_id=None):
        captured["tenant_id"] = tenant_id
        # Repo returns None because the row's tenant_id doesn't match the
        # principal's tenant_id in the WHERE clause.
        return None

    from apps.api.routes import exports as exports_mod

    monkeypatch.setattr(exports_mod, "get_ma_export_job_by_id", _fake_get)

    async def _session_override():
        return MagicMock()

    app.dependency_overrides[get_session] = _session_override

    # Try to fetch a job that lives under a DIFFERENT tenant.
    other_tenant_job_id = uuid4()
    response = await client.get(f"/v1/exports/ma-diligence/jobs/{other_tenant_job_id}")
    assert response.status_code == 404
    # Tenant scoping was applied (repo called with principal's tenant_id).
    assert captured["tenant_id"] == _TENANT_ID
    app.dependency_overrides.clear()


# ---------- LIST jobs ----------


@pytest.mark.asyncio
async def test_list_returns_jobs_for_principal_tenant(app, client, monkeypatch) -> None:
    rows = [
        _make_job_row(status="completed"),
        _make_job_row(status="failed"),
        _make_job_row(status="running"),
    ]

    captured: dict = {}

    async def _fake_list(session, tenant_id, *, limit=50, offset=0):
        captured["tenant_id"] = tenant_id
        captured["limit"] = limit
        captured["offset"] = offset
        return rows

    from apps.api.routes import exports as exports_mod

    monkeypatch.setattr(exports_mod, "list_ma_export_jobs_for_tenant", _fake_list)

    async def _session_override():
        return MagicMock()

    app.dependency_overrides[get_session] = _session_override

    response = await client.get("/v1/exports/ma-diligence/jobs")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tenant_id"] == str(_TENANT_ID)
    assert body["count"] == 3
    assert len(body["items"]) == 3
    assert {item["status"] for item in body["items"]} == {
        "completed",
        "failed",
        "running",
    }
    # The list helper was called with the principal's tenant_id (no
    # tenant_id query param exists).
    assert captured["tenant_id"] == _TENANT_ID
    assert captured["limit"] == 50
    assert captured["offset"] == 0
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_empty_returns_zero_count(app, client, monkeypatch) -> None:
    async def _fake_list(session, tenant_id, *, limit=50, offset=0):
        return []

    from apps.api.routes import exports as exports_mod

    monkeypatch.setattr(exports_mod, "list_ma_export_jobs_for_tenant", _fake_list)

    async def _session_override():
        return MagicMock()

    app.dependency_overrides[get_session] = _session_override

    response = await client.get("/v1/exports/ma-diligence/jobs")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 0
    assert body["items"] == []
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_passes_through_limit_and_offset(app, client, monkeypatch) -> None:
    captured: dict = {}

    async def _fake_list(session, tenant_id, *, limit=50, offset=0):
        captured["limit"] = limit
        captured["offset"] = offset
        return []

    from apps.api.routes import exports as exports_mod

    monkeypatch.setattr(exports_mod, "list_ma_export_jobs_for_tenant", _fake_list)

    async def _session_override():
        return MagicMock()

    app.dependency_overrides[get_session] = _session_override

    response = await client.get("/v1/exports/ma-diligence/jobs?limit=10&offset=20")
    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 10
    assert body["offset"] == 20
    assert captured["limit"] == 10
    assert captured["offset"] == 20
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_rejects_limit_over_max(app, client) -> None:
    async def _session_override():
        return MagicMock()

    app.dependency_overrides[get_session] = _session_override

    response = await client.get("/v1/exports/ma-diligence/jobs?limit=201")
    assert response.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_rejects_negative_offset(app, client) -> None:
    async def _session_override():
        return MagicMock()

    app.dependency_overrides[get_session] = _session_override

    response = await client.get("/v1/exports/ma-diligence/jobs?offset=-1")
    assert response.status_code == 422
    app.dependency_overrides.clear()


# ---------- get_sessionmaker default stub ----------


@pytest.mark.asyncio
async def test_get_sessionmaker_default_raises_not_implemented() -> None:
    """The stub dependency raises so deployment-time configuration is
    required (no silent fallback to a None sessionmaker)."""
    with pytest.raises(NotImplementedError):
        await get_sessionmaker()

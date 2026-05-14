"""Tests for apps.api.auth.dependencies — get_principal + get_token_verifier."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from apps.api.auth.dependencies import (
    _DEFAULT_VERIFIER_HOLDER,
    _get_or_build_default_verifier,
    get_principal,
    get_token_verifier,
)
from apps.api.auth.principal import Principal
from apps.api.auth.token import (
    HmacBearerTokenVerifier,
    TokenVerifier,
    mint_hmac_token,
)

_GOOD_SECRET = b"k" * 32


def _make_test_app(verifier: TokenVerifier) -> FastAPI:
    """Build a FastAPI app with one route that returns the resolved Principal.

    The verifier is wired as a dependency override so the route doesn't
    depend on env vars.
    """
    app = FastAPI()

    @app.get("/whoami")
    async def whoami(p: Principal = Depends(get_principal)):  # noqa: B008
        return {
            "tenant_id": str(p.tenant_id),
            "agent_id": str(p.agent_id),
            "agent_slug": p.agent_slug,
            "scopes": sorted(p.scopes),
        }

    async def _verifier_override() -> TokenVerifier:
        return verifier

    app.dependency_overrides[get_token_verifier] = _verifier_override
    return app


@pytest.fixture(autouse=True)
def _clear_default_verifier_cache():
    """Make sure the env-driven verifier cache is empty for each test."""
    _DEFAULT_VERIFIER_HOLDER["verifier"] = None
    yield
    _DEFAULT_VERIFIER_HOLDER["verifier"] = None


# ---------------------------------------------------------------------------
# get_principal: happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_principal_happy_path_with_valid_token():
    tid = uuid4()
    aid = uuid4()
    verifier = HmacBearerTokenVerifier(tenant_id=tid, secret=_GOOD_SECRET)
    token = mint_hmac_token(
        tenant_id=tid,
        agent_id=aid,
        agent_slug="agent-alpha",
        secret=_GOOD_SECRET,
        scopes=["events:write"],
    )
    app = _make_test_app(verifier)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["tenant_id"] == str(tid)
    assert body["agent_id"] == str(aid)
    assert body["agent_slug"] == "agent-alpha"
    assert body["scopes"] == ["events:write"]


# ---------------------------------------------------------------------------
# get_principal: failure modes -> 401 with differentiated error codes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_principal_missing_authorization_returns_401_auth_required():
    verifier = HmacBearerTokenVerifier(tenant_id=uuid4(), secret=_GOOD_SECRET)
    app = _make_test_app(verifier)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/whoami")
    assert r.status_code == 401
    assert r.json()["detail"]["error"] == "auth_required"


@pytest.mark.asyncio
async def test_get_principal_malformed_authorization_returns_401_invalid():
    """Header doesn't say 'Bearer <token>' shape."""
    verifier = HmacBearerTokenVerifier(tenant_id=uuid4(), secret=_GOOD_SECRET)
    app = _make_test_app(verifier)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/whoami", headers={"Authorization": "NotBearer xxxx"})
    assert r.status_code == 401
    assert r.json()["detail"]["error"] == "token_invalid"


@pytest.mark.asyncio
async def test_get_principal_bearer_without_token_returns_401_invalid():
    """Header is 'Bearer ' (no token after the space)."""
    verifier = HmacBearerTokenVerifier(tenant_id=uuid4(), secret=_GOOD_SECRET)
    app = _make_test_app(verifier)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/whoami", headers={"Authorization": "Bearer"})
    assert r.status_code == 401
    assert r.json()["detail"]["error"] == "token_invalid"


@pytest.mark.asyncio
async def test_get_principal_bad_token_returns_401_invalid():
    verifier = HmacBearerTokenVerifier(tenant_id=uuid4(), secret=_GOOD_SECRET)
    app = _make_test_app(verifier)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/whoami", headers={"Authorization": "Bearer junk"})
    assert r.status_code == 401
    assert r.json()["detail"]["error"] == "token_invalid"
    # Generic message - must NOT reveal which check failed.
    assert r.json()["detail"]["reason"] == "invalid token"


@pytest.mark.asyncio
async def test_get_principal_expired_token_returns_401_expired():
    tid = uuid4()
    past_exp = (datetime.now(UTC) - timedelta(hours=1)).timestamp()
    token = mint_hmac_token(
        tenant_id=tid,
        agent_id=uuid4(),
        agent_slug="a",
        secret=_GOOD_SECRET,
        exp=past_exp,
    )
    verifier = HmacBearerTokenVerifier(tenant_id=tid, secret=_GOOD_SECRET)
    app = _make_test_app(verifier)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert r.json()["detail"]["error"] == "token_expired"


@pytest.mark.asyncio
async def test_get_principal_case_insensitive_bearer():
    """Per RFC 6750 §2.1 'Bearer' is case-insensitive. Verify the dep accepts
    lowercase 'bearer ' as well."""
    tid = uuid4()
    token = mint_hmac_token(tenant_id=tid, agent_id=uuid4(), agent_slug="a", secret=_GOOD_SECRET)
    verifier = HmacBearerTokenVerifier(tenant_id=tid, secret=_GOOD_SECRET)
    app = _make_test_app(verifier)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/whoami", headers={"Authorization": f"bearer {token}"})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# get_token_verifier (default factory) - env-driven construction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_token_verifier_returns_503_when_env_not_set(monkeypatch):
    """No FORENSA_HMAC_SECRET / TENANT_ID -> auth_not_configured 503."""
    monkeypatch.delenv("FORENSA_HMAC_SECRET", raising=False)
    monkeypatch.delenv("FORENSA_HMAC_TENANT_ID", raising=False)
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as ei:
        await get_token_verifier()
    assert ei.value.status_code == 503
    assert ei.value.detail["error"] == "auth_not_configured"


def test_default_verifier_built_from_env(monkeypatch):
    tid = uuid4()
    secret_hex = (b"s" * 32).hex()
    monkeypatch.setenv("FORENSA_HMAC_SECRET", secret_hex)
    monkeypatch.setenv("FORENSA_HMAC_TENANT_ID", str(tid))
    v = _get_or_build_default_verifier()
    assert v is not None
    # Cached on subsequent calls.
    v2 = _get_or_build_default_verifier()
    assert v is v2


def test_default_verifier_cache_hit_skips_rebuild(monkeypatch):
    """Explicitly cover line 120 - the ``cached is not None`` early-return.

    Pre-seed the holder with a verifier; the factory must return it without
    consulting env vars (proved by leaving env unset).
    """
    monkeypatch.delenv("FORENSA_HMAC_SECRET", raising=False)
    monkeypatch.delenv("FORENSA_HMAC_TENANT_ID", raising=False)
    sentinel = HmacBearerTokenVerifier(tenant_id=uuid4(), secret=b"s" * 32)
    _DEFAULT_VERIFIER_HOLDER["verifier"] = sentinel
    result = _get_or_build_default_verifier()
    assert result is sentinel


def test_default_verifier_returns_none_when_secret_hex_malformed(monkeypatch, caplog):
    monkeypatch.setenv("FORENSA_HMAC_SECRET", "not-hex-XYZ")
    monkeypatch.setenv("FORENSA_HMAC_TENANT_ID", str(uuid4()))
    import logging

    caplog.set_level(logging.ERROR, logger="apps.api.auth.dependencies")
    v = _get_or_build_default_verifier()
    assert v is None
    assert "forensa.auth.invalid_secret_hex" in {r.message for r in caplog.records}


def test_default_verifier_returns_none_when_tenant_id_malformed(monkeypatch, caplog):
    monkeypatch.setenv("FORENSA_HMAC_SECRET", (b"s" * 32).hex())
    monkeypatch.setenv("FORENSA_HMAC_TENANT_ID", "not-a-uuid")
    import logging

    caplog.set_level(logging.ERROR, logger="apps.api.auth.dependencies")
    v = _get_or_build_default_verifier()
    assert v is None
    assert "forensa.auth.invalid_tenant_id_env" in {r.message for r in caplog.records}


def test_default_verifier_returns_none_when_secret_too_short(monkeypatch, caplog):
    # Valid hex, but only 16 bytes (32 hex chars) - below the 32-byte minimum.
    monkeypatch.setenv("FORENSA_HMAC_SECRET", (b"s" * 16).hex())
    monkeypatch.setenv("FORENSA_HMAC_TENANT_ID", str(uuid4()))
    import logging

    caplog.set_level(logging.ERROR, logger="apps.api.auth.dependencies")
    v = _get_or_build_default_verifier()
    assert v is None
    assert "forensa.auth.weak_secret" in {r.message for r in caplog.records}


def test_default_verifier_returns_none_when_secret_env_empty(monkeypatch):
    monkeypatch.setenv("FORENSA_HMAC_SECRET", "")
    monkeypatch.setenv("FORENSA_HMAC_TENANT_ID", str(uuid4()))
    v = _get_or_build_default_verifier()
    assert v is None


def test_default_verifier_returns_none_when_tenant_id_env_empty(monkeypatch):
    monkeypatch.setenv("FORENSA_HMAC_SECRET", (b"s" * 32).hex())
    monkeypatch.setenv("FORENSA_HMAC_TENANT_ID", "")
    v = _get_or_build_default_verifier()
    assert v is None

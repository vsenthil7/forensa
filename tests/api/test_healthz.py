from __future__ import annotations

import logging

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from apps.api.main import __version__, app, create_app

pytestmark = pytest.mark.asyncio


async def test_healthz_returns_ok_and_version() -> None:
    transport = ASGITransport(app=app)
    async with LifespanManager(app):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    # Core fields
    assert body["status"] == "ok"
    assert body["version"] == __version__
    # CP9.4: narrative-client transparency exposed via /healthz so product
    # users + procurement can see which LLM is processing their evidence.
    assert "narrative_provider" in body
    assert "narrative_model_id" in body
    assert "narrative_is_fallback" in body
    assert isinstance(body["narrative_is_fallback"], bool)


async def test_lifespan_logs_startup_and_shutdown(caplog) -> None:
    fresh = create_app()
    caplog.set_level(logging.INFO, logger="apps.api.main")
    async with LifespanManager(fresh):
        pass
    messages = [r.message for r in caplog.records]
    assert "forensa.api.startup" in messages
    assert "forensa.api.shutdown" in messages

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
    assert body == {"status": "ok", "version": __version__}


async def test_lifespan_logs_startup_and_shutdown(caplog) -> None:
    fresh = create_app()
    caplog.set_level(logging.INFO, logger="apps.api.main")
    async with LifespanManager(fresh):
        pass
    messages = [r.message for r in caplog.records]
    assert "forensa.api.startup" in messages
    assert "forensa.api.shutdown" in messages

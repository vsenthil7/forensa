"""Tests for apps.api.main lifespan production-DB wiring (CP9.46 / IP #5).

The lifespan hook in create_app() wires production AsyncEngine +
sessionmaker into the FastAPI app via app.dependency_overrides at
startup, and disposes the engine at shutdown.

Two paths to cover:
  1. FORENSA_DB_URL is set -> the override branch fires and both
     get_session and get_sessionmaker land in app.dependency_overrides.
  2. FORENSA_DB_URL is unset -> the warning branch fires and the
     dependency overrides stay empty (route layer will surface a
     stub-raising 503 when hit -- documented behaviour).

We use ASGITransport+AsyncClient so the lifespan actually runs.
The DB URL points at a non-routable address so make_engine() can
construct without connecting (sqlalchemy is lazy on connect); the
test never hits a route that would actually use the session.
"""

from __future__ import annotations

import pytest

from apps.api.main import create_app
from apps.api.routes.exports import get_sessionmaker
from apps.api.routes.receipts import get_session


@pytest.mark.asyncio
async def test_lifespan_wires_prod_deps_when_db_url_is_set(monkeypatch) -> None:
    """With FORENSA_DB_URL set, the lifespan installs both production
    dependency overrides AND the engine is disposed on shutdown."""
    monkeypatch.setenv("FORENSA_DB_URL", "postgresql+asyncpg://test:test@127.0.0.1:1/test")

    # Track engine.dispose() calls to assert shutdown hook fires.
    disposed: list[bool] = []

    from packages.ledger import session as session_mod

    real_make_engine = session_mod.make_engine

    class _RecordingEngine:
        def __init__(self, real):
            self._real = real

        async def dispose(self) -> None:
            disposed.append(True)
            # Engine wasn't actually connected; nothing to clean up.

    def _fake_make_engine(url: str):
        real = real_make_engine(url)
        return _RecordingEngine(real)

    from apps.api import main as main_mod

    monkeypatch.setattr(main_mod, "make_engine", _fake_make_engine)

    app = create_app()

    # Drive the lifespan context directly. FastAPI exposes its lifespan
    # context manager via app.router.lifespan_context. AsgiTransport doesn't
    # fire it on a per-request basis under httpx -- we invoke it here so
    # the startup + shutdown hooks both run.
    async with app.router.lifespan_context(app):
        # Inside the lifespan: prod overrides should be in place.
        assert get_session in app.dependency_overrides
        assert get_sessionmaker in app.dependency_overrides

    # After the context exits, shutdown ran -> engine.dispose called.
    assert disposed == [True], (
        f"Expected engine.dispose() to be called exactly once during " f"shutdown; got {disposed}"
    )
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_lifespan_warns_and_skips_wiring_when_db_url_unset(monkeypatch, caplog) -> None:
    """With FORENSA_DB_URL unset, the lifespan emits a warning log and
    leaves dependency_overrides empty (route layer will 503 on those
    deps, which is the documented behaviour for un-configured prod)."""
    monkeypatch.delenv("FORENSA_DB_URL", raising=False)
    app = create_app()

    import logging

    with caplog.at_level(logging.WARNING, logger="apps.api.main"):
        async with app.router.lifespan_context(app):
            # No prod wiring happened.
            assert get_session not in app.dependency_overrides
            assert get_sessionmaker not in app.dependency_overrides

    # The warning log fired.
    warned = [r for r in caplog.records if "no_db_url" in r.getMessage()]
    assert len(warned) >= 1, f"Expected forensa.api.no_db_url warning; got {caplog.records}"


@pytest.mark.asyncio
async def test_lifespan_respects_existing_test_overrides(monkeypatch) -> None:
    """If a test installs its own overrides BEFORE the lifespan runs,
    the production wiring must NOT clobber them. This is the contract
    that lets test fixtures continue to work even after CP9.46 added
    production wiring."""
    monkeypatch.setenv("FORENSA_DB_URL", "postgresql+asyncpg://test:test@127.0.0.1:1/test")
    app = create_app()

    async def _test_override_session():
        yield None  # placeholder; tests never await actual session here

    async def _test_override_sessionmaker():
        return None  # placeholder

    # Install test overrides BEFORE lifespan fires.
    app.dependency_overrides[get_session] = _test_override_session
    app.dependency_overrides[get_sessionmaker] = _test_override_sessionmaker

    async with app.router.lifespan_context(app):
        # Test overrides survived the lifespan (production wiring deferred).
        assert app.dependency_overrides[get_session] is _test_override_session
        assert app.dependency_overrides[get_sessionmaker] is _test_override_sessionmaker

    app.dependency_overrides.clear()


def test_create_app_returns_fastapi_with_healthz_route() -> None:
    """Smoke test: the factory produces an app with /healthz mounted.

    Synchronous (no event loop) because we only inspect the route table.
    """
    app = create_app()
    paths = {r.path for r in app.routes}
    assert "/healthz" in paths
    # Title + version surface in the OpenAPI metadata.
    assert app.title == "Forensa"
    assert app.version == "0.1.0"

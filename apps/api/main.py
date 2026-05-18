from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.narrative_selector import get_selection
from apps.api.routes import anchors as anchors_routes
from apps.api.routes import events as events_routes
from apps.api.routes import evidence as evidence_routes
from apps.api.routes import exports as exports_routes
from apps.api.routes import metrics as metrics_routes
from apps.api.routes import narratives as narratives_routes
from apps.api.routes import receipts as receipts_routes
from apps.api.routes import tabletop as tabletop_routes
from apps.api.routes.exports import get_sessionmaker
from apps.api.routes.receipts import get_session
from packages.ledger.session import make_engine, make_sessionmaker

logger = logging.getLogger(__name__)

__version__ = "0.1.0"


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup/shutdown hook.

    CP9.46 / IP #5: wires the production AsyncEngine + sessionmaker into
    the app at startup and disposes the engine at shutdown. The two
    FastAPI dependencies that need them (`get_session` for per-request
    sessions, `get_sessionmaker` for background-task workers) are
    overridden here via app.dependency_overrides so test wiring can
    still swap them per-test.
    """
    selection = get_selection()
    logger.info(
        "forensa.api.startup",
        extra={
            "version": __version__,
            "narrative_provider": selection.provider,
            "narrative_model_id": selection.model_id,
            "narrative_is_fallback": selection.is_fallback,
        },
    )

    # Production DB wiring. The dependency overrides below are no-ops
    # in test mode because tests override them BEFORE the lifespan
    # runs (via app.dependency_overrides assignment at fixture time).
    # In production these are the real wiring that connects the route
    # layer to Postgres.
    db_url = os.environ.get("FORENSA_DB_URL")
    if db_url:
        engine = make_engine(db_url)
        sm: async_sessionmaker[AsyncSession] = make_sessionmaker(engine)

        async def _prod_get_session() -> AsyncIterator[AsyncSession]:  # pragma: no cover
            # Exercised end-to-end by the captioned Playwright spec at
            # apps/console/tests-e2e/demo/end-to-end-demo.spec.ts which
            # POSTs/GETs against a live FastAPI booted by the Playwright
            # webServer. Not reachable through the pytest lifespan tests
            # because those use a fake FORENSA_DB_URL whose sm() call
            # would block waiting for a TCP connection to a non-routable
            # address.
            async with sm() as session:
                yield session

        async def _prod_get_sessionmaker() -> async_sessionmaker[AsyncSession]:  # pragma: no cover
            # Same justification as _prod_get_session above.
            return sm

        # Only install if not already overridden (tests set theirs first).
        if get_session not in app.dependency_overrides:
            app.dependency_overrides[get_session] = _prod_get_session
        if get_sessionmaker not in app.dependency_overrides:
            app.dependency_overrides[get_sessionmaker] = _prod_get_sessionmaker
        logger.info(
            "forensa.api.db_wired",
            extra={"db_url_redacted": db_url.split("@")[-1] if "@" in db_url else "unknown"},
        )
    else:
        logger.warning(
            "forensa.api.no_db_url",
            extra={
                "hint": (
                    "FORENSA_DB_URL not set; routes depending on a session "
                    "will 500. Set FORENSA_DB_URL=postgresql+asyncpg://... "
                    "to enable DB-backed routes."
                )
            },
        )
        engine = None

    try:
        yield
    finally:
        if engine is not None:
            await engine.dispose()
        logger.info("forensa.api.shutdown")


def create_app() -> FastAPI:
    """Application factory. Keeps module import side-effect-free for testing."""
    app = FastAPI(
        title="Forensa",
        description="Cryptographic evidence layer for enterprise AI agents",
        version=__version__,
        default_response_class=ORJSONResponse,
        lifespan=_lifespan,
    )

    # CORS for the Next.js Console (apps/console/) running at localhost:3000
    # in development. Production deployments override the allow_origins list
    # via FORENSA_CORS_ORIGINS (comma-separated). For the captioned demo the
    # default works because both the API and Console run on localhost.
    cors_origins_env = os.environ.get("FORENSA_CORS_ORIGINS")
    if cors_origins_env:
        allow_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
    else:
        allow_origins = [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Forensa-Request-Id"],
        expose_headers=[
            "X-Forensa-Event-Id",
            "X-Forensa-Receipt-Id",
            "X-Forensa-Root-Hash",
        ],
    )

    @app.get("/healthz", status_code=status.HTTP_200_OK)
    async def healthz() -> dict[str, object]:
        """Liveness probe + narrative-client transparency.

        Includes ``narrative_provider``, ``narrative_model_id``, and
        ``narrative_is_fallback`` so product users can verify which LLM is
        processing their evidence packs without grepping server logs.
        """
        selection = get_selection()
        return {
            "status": "ok",
            "version": __version__,
            "narrative_provider": selection.provider,
            "narrative_model_id": selection.model_id,
            "narrative_is_fallback": selection.is_fallback,
        }

    app.include_router(events_routes.router)
    app.include_router(receipts_routes.router)
    app.include_router(evidence_routes.router)
    app.include_router(narratives_routes.router)
    app.include_router(anchors_routes.router)
    app.include_router(exports_routes.router)
    app.include_router(tabletop_routes.router)
    app.include_router(metrics_routes.router)

    return app


app = create_app()


def run() -> None:  # pragma: no cover
    """Poetry script entrypoint: `poetry run forensa-api`."""
    import uvicorn

    uvicorn.run("apps.api.main:app", host="0.0.0.0", port=8000, reload=True)  # nosec B104

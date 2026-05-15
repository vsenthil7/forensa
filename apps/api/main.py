from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.responses import ORJSONResponse

from apps.api.narrative_selector import get_selection
from apps.api.routes import anchors as anchors_routes
from apps.api.routes import events as events_routes
from apps.api.routes import evidence as evidence_routes
from apps.api.routes import exports as exports_routes
from apps.api.routes import narratives as narratives_routes
from apps.api.routes import receipts as receipts_routes

logger = logging.getLogger(__name__)

__version__ = "0.1.0"


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup/shutdown hook."""
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
    yield
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

    return app


app = create_app()


def run() -> None:  # pragma: no cover
    """Poetry script entrypoint: `poetry run forensa-api`."""
    import uvicorn

    uvicorn.run("apps.api.main:app", host="0.0.0.0", port=8000, reload=True)  # nosec B104

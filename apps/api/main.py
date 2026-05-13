from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, status
from fastapi.responses import ORJSONResponse

from apps.api.routes import events as events_routes

logger = logging.getLogger(__name__)

__version__ = "0.1.0"


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup/shutdown hook."""
    logger.info("forensa.api.startup", extra={"version": __version__})
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
    async def healthz() -> dict[str, str]:
        """Liveness probe. No downstream dependencies checked."""
        return {"status": "ok", "version": __version__}

    app.include_router(events_routes.router)

    return app


app = create_app()


def run() -> None:  # pragma: no cover
    """Poetry script entrypoint: `poetry run forensa-api`."""
    import uvicorn

    uvicorn.run("apps.api.main:app", host="0.0.0.0", port=8000, reload=True)

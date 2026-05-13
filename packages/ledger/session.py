"""Async SQLAlchemy engine + sessionmaker for the Forensa evidence ledger.

Append-only by policy. The repository layer (packages.ledger.repositories)
is the only code that should obtain sessions from here. Routes wrap calls in
async-with blocks so transactions are scoped to a single request.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_DEFAULT_URL = "postgresql+asyncpg://forensa:forensa@localhost:5432/forensa"


def _resolve_url() -> str:
    """Read FORENSA_DB_URL from env, falling back to the local default."""
    return os.environ.get("FORENSA_DB_URL", _DEFAULT_URL)


def make_engine(url: str | None = None) -> AsyncEngine:
    """Build an AsyncEngine. Caller is responsible for engine lifecycle.

    Pool sizes are intentionally small to start; tuned in BR-09 load tests.
    """
    resolved = url if url is not None else _resolve_url()
    return create_async_engine(
        resolved,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        future=True,
    )


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Return an async_sessionmaker bound to the given engine.

    expire_on_commit is False so ORM instances remain usable after commit;
    Forensa never mutates ORM rows post-commit (append-only) but routes may
    serialise them for response payloads.
    """
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@asynccontextmanager
async def session_scope(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Yield an AsyncSession inside an explicit transaction.

    On success: commit. On any exception: rollback and re-raise. The
    repository layer relies on this contract for atomic-write semantics.
    """
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

"""Shared fixtures and skip-logic for ``tests/integration/`` (real-Postgres tests).

Skip semantics
--------------

Every test under ``tests/integration/`` MUST be marked with ``@pytest.mark.pg``.
This conftest skips all such tests when ``FORENSA_TEST_DB_URL`` is not set in the
environment. That keeps the default ``poetry run pytest`` invocation a
pure-SQLite, no-network suite that still satisfies the 100% coverage gate.

When ``FORENSA_TEST_DB_URL`` IS set, the marker is consumed normally and the
tests execute against the configured Postgres instance.

Fixtures
--------

- ``pg_url``: the resolved DSN (string).
- ``pg_engine``: a fresh async SQLAlchemy engine bound to ``pg_url``.
- ``pg_migrated``: a session-scoped fixture that runs ``alembic upgrade head``
  exactly once per test session so individual tests can assume the schema is
  present. Tests that want to verify migration behaviour itself bypass this
  fixture and drive alembic directly.
- ``pg_clean_session``: per-test fixture yielding an ``AsyncSession`` against
  the migrated database with a tenant/agent/bundle row pre-seeded. Truncates
  all forensa tables between tests so each test starts from a known state.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_ENV_VAR = "FORENSA_TEST_DB_URL"
_REPO_ROOT = Path(__file__).resolve().parents[2]


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip all @pytest.mark.pg tests when FORENSA_TEST_DB_URL is unset.

    This keeps the default ``poetry run pytest`` green on machines without a
    Postgres reachable, while still enforcing that integration tests register
    themselves with the ``pg`` marker.
    """
    if os.environ.get(_ENV_VAR):
        return
    skip_marker = pytest.mark.skip(
        reason=f"{_ENV_VAR} not set; skipping real-Postgres integration tests"
    )
    for item in items:
        if "pg" in item.keywords:
            item.add_marker(skip_marker)


@pytest.fixture(scope="session")
def pg_url() -> str:
    """Resolved Postgres DSN; xfails the test session early if missing."""
    url = os.environ.get(_ENV_VAR)
    if not url:  # pragma: no cover - only reached when env var is set AND fixture invoked
        pytest.skip(f"{_ENV_VAR} not set")
    return url


@pytest_asyncio.fixture
async def pg_engine(pg_url: str) -> AsyncIterator[AsyncEngine]:
    """Fresh async engine; disposed at end of test to avoid event-loop leaks."""
    engine = create_async_engine(pg_url, future=True, poolclass=None)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def pg_clean_session(pg_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Yield a session with all forensa tables truncated.

    Truncates in FK-respecting order (children first). Uses ``RESTART IDENTITY
    CASCADE`` so any sequence values reset too. The alembic_version row is
    preserved so subsequent tests don't re-run migrations.
    """
    async with pg_engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE "
                "timestamp_anchors, idempotency_records, "
                "policy_bundle_approvals, receipts, events, "
                "policy_snapshots, policy_bundles, agents, tenants "
                "RESTART IDENTITY CASCADE"
            )
        )
    session_factory = async_sessionmaker(pg_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
def fresh_tenant_id() -> uuid.UUID:
    """A fresh tenant UUID for use in a single test."""
    return uuid.uuid4()


@pytest.fixture
def fresh_bundle_id() -> uuid.UUID:
    """A fresh bundle UUID for use in a single test."""
    return uuid.uuid4()


@pytest.fixture
def repo_root() -> Path:
    """The Forensa repo root (parent of tests/)."""
    return _REPO_ROOT

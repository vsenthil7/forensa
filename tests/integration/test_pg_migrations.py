"""Migration round-trip on real Postgres.

Closes NEW-P9.15.1.run-migration-on-pg from CP9.15.1's honest-gaps list.

What this verifies that SQLite + the offline ``alembic upgrade --sql`` preview
cannot:

- The four production migrations actually apply forward against a real
  PostgreSQL 16 backend (CREATE TABLE / ALTER TABLE / CREATE INDEX / CHECK
  constraints / partial UNIQUE / trigger function + trigger definitions).
- Migration 0004 is reversible: downgrade -1 drops the bundle_approvals table,
  the partial UNIQUE index, the triggers and the status column, then upgrade
  head reinstates everything cleanly.
- The expected schema objects (specific tables, indexes, triggers) exist on
  the live database after upgrade head, not just in the migration script's
  documented intent.
"""

from __future__ import annotations

import subprocess
import sys

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.pg


def _run_alembic(args: list[str], pg_url: str, repo_root) -> subprocess.CompletedProcess[str]:
    """Run alembic via subprocess with FORENSA_DATABASE_URL pinned to the test DB.

    Subprocess (not in-process API) keeps the migration's own asyncio event
    loop isolated from pytest-asyncio's loop. Avoids the
    "loop is closed / cannot reuse loop" footgun on Windows.
    """
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(repo_root),
        env={
            **__import__("os").environ,
            "FORENSA_DATABASE_URL": pg_url,
        },
        capture_output=True,
        text=True,
        check=False,
    )


async def _table_exists(engine: AsyncEngine, table: str) -> bool:
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT 1 FROM information_schema.tables WHERE table_name = :t"),
            {"t": table},
        )
        return result.scalar() is not None


async def _index_exists(engine: AsyncEngine, index: str) -> bool:
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT 1 FROM pg_indexes WHERE indexname = :i"),
            {"i": index},
        )
        return result.scalar() is not None


async def _trigger_exists(engine: AsyncEngine, trigger: str) -> bool:
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT 1 FROM information_schema.triggers WHERE trigger_name = :t"),
            {"t": trigger},
        )
        return result.scalar() is not None


async def _current_revision(engine: AsyncEngine) -> str | None:
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT version_num FROM alembic_version"))
        row = result.first()
        return row[0] if row else None


async def test_upgrade_head_brings_schema_to_0004(
    pg_engine: AsyncEngine, pg_url: str, repo_root
) -> None:
    """Forward path: empty DB -> all four migrations -> 0004 head schema."""
    _run_alembic(["downgrade", "base"], pg_url, repo_root)

    result = _run_alembic(["upgrade", "head"], pg_url, repo_root)
    assert result.returncode == 0, f"upgrade failed: {result.stderr}"

    assert await _current_revision(pg_engine) == "0004_bundle_approval_workflow"

    for table in (
        "tenants",
        "agents",
        "policy_bundles",
        "policy_snapshots",
        "events",
        "receipts",
        "policy_bundle_approvals",
    ):
        assert await _table_exists(pg_engine, table), f"missing table: {table}"

    assert await _index_exists(pg_engine, "uq_policy_bundles_one_active_per_tenant")
    assert await _trigger_exists(pg_engine, "trg_policy_bundle_approvals_block_update")
    assert await _trigger_exists(pg_engine, "trg_policy_bundle_approvals_block_delete")


async def test_downgrade_one_drops_0004_objects(
    pg_engine: AsyncEngine, pg_url: str, repo_root
) -> None:
    """Reverse path: 0004 -> 0003 must remove every object 0004 created."""
    _run_alembic(["upgrade", "head"], pg_url, repo_root)
    assert await _current_revision(pg_engine) == "0004_bundle_approval_workflow"

    result = _run_alembic(["downgrade", "-1"], pg_url, repo_root)
    assert result.returncode == 0, f"downgrade failed: {result.stderr}"

    assert await _current_revision(pg_engine) == "0003_event_output"

    assert not await _table_exists(pg_engine, "policy_bundle_approvals")
    assert not await _index_exists(pg_engine, "uq_policy_bundles_one_active_per_tenant")
    assert not await _trigger_exists(pg_engine, "trg_policy_bundle_approvals_block_update")
    assert not await _trigger_exists(pg_engine, "trg_policy_bundle_approvals_block_delete")


async def test_upgrade_after_downgrade_round_trip(
    pg_engine: AsyncEngine, pg_url: str, repo_root
) -> None:
    """Full round-trip: head -> head-1 -> head must finish at head with full schema.

    Catches the subtle migration bug where downgrade leaves orphan state
    (sequence, type, function) that prevents a clean re-upgrade.
    """
    _run_alembic(["upgrade", "head"], pg_url, repo_root)
    _run_alembic(["downgrade", "-1"], pg_url, repo_root)

    result = _run_alembic(["upgrade", "head"], pg_url, repo_root)
    assert result.returncode == 0, f"re-upgrade failed: {result.stderr}"

    assert await _current_revision(pg_engine) == "0004_bundle_approval_workflow"
    assert await _table_exists(pg_engine, "policy_bundle_approvals")
    assert await _index_exists(pg_engine, "uq_policy_bundles_one_active_per_tenant")
    assert await _trigger_exists(pg_engine, "trg_policy_bundle_approvals_block_update")
    assert await _trigger_exists(pg_engine, "trg_policy_bundle_approvals_block_delete")

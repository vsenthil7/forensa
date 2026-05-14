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


async def test_upgrade_head_brings_schema_to_0006(
    pg_engine: AsyncEngine, pg_url: str, repo_root
) -> None:
    """Forward path: empty DB -> all six migrations -> 0006 head schema."""
    _run_alembic(["downgrade", "base"], pg_url, repo_root)

    result = _run_alembic(["upgrade", "head"], pg_url, repo_root)
    assert result.returncode == 0, f"upgrade failed: {result.stderr}"

    assert await _current_revision(pg_engine) == "0006_agent_signature"

    for table in (
        "tenants",
        "agents",
        "policy_bundles",
        "policy_snapshots",
        "events",
        "receipts",
        "policy_bundle_approvals",
        "idempotency_records",
    ):
        assert await _table_exists(pg_engine, table), f"missing table: {table}"

    assert await _index_exists(pg_engine, "uq_policy_bundles_one_active_per_tenant")
    assert await _trigger_exists(pg_engine, "trg_policy_bundle_approvals_block_update")
    assert await _trigger_exists(pg_engine, "trg_policy_bundle_approvals_block_delete")
    assert await _index_exists(pg_engine, "ix_idempotency_records_expires_at")

    # CP9.18: receipts table has agent_signature column.
    async with pg_engine.connect() as conn:
        result_col = await conn.execute(
            text(
                "SELECT data_type, is_nullable FROM information_schema.columns "
                "WHERE table_name = 'receipts' AND column_name = 'agent_signature'"
            )
        )
        row = result_col.first()
        assert row is not None, "missing column: receipts.agent_signature"
        # bytea in Postgres for LargeBinary, nullable=YES (per migration 0006).
        assert row[1] == "YES"


async def test_downgrade_one_drops_0006_objects(
    pg_engine: AsyncEngine, pg_url: str, repo_root
) -> None:
    """Reverse path: 0006 -> 0005 must remove agent_signature column cleanly."""
    _run_alembic(["upgrade", "head"], pg_url, repo_root)
    assert await _current_revision(pg_engine) == "0006_agent_signature"

    result = _run_alembic(["downgrade", "-1"], pg_url, repo_root)
    assert result.returncode == 0, f"downgrade failed: {result.stderr}"

    assert await _current_revision(pg_engine) == "0005_idempotency_records"

    async with pg_engine.connect() as conn:
        result_col = await conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'receipts' AND column_name = 'agent_signature'"
            )
        )
        assert result_col.first() is None
    # idempotency_records must still be present.
    assert await _table_exists(pg_engine, "idempotency_records")


async def test_downgrade_two_steps_via_intermediate_0005(
    pg_engine: AsyncEngine, pg_url: str, repo_root
) -> None:
    """From 0005 (one-step-down-from-head), step -1 again -> 0004.

    Smoke-test path: ensures intermediate 0005 state is itself reversible to
    0004 cleanly, decoupled from the head-down-to-0004 path that
    ``test_downgrade_two_drops_0005_objects`` exercises.
    """
    _run_alembic(["upgrade", "head"], pg_url, repo_root)
    _run_alembic(["downgrade", "-1"], pg_url, repo_root)
    assert await _current_revision(pg_engine) == "0005_idempotency_records"

    result = _run_alembic(["downgrade", "-1"], pg_url, repo_root)
    assert result.returncode == 0, f"downgrade failed: {result.stderr}"

    assert await _current_revision(pg_engine) == "0004_bundle_approval_workflow"
    assert not await _table_exists(pg_engine, "idempotency_records")
    assert not await _index_exists(pg_engine, "ix_idempotency_records_expires_at")
    # The 0004 objects must STILL be present after only stepping back one.
    assert await _table_exists(pg_engine, "policy_bundle_approvals")


async def test_downgrade_two_drops_0005_objects(
    pg_engine: AsyncEngine, pg_url: str, repo_root
) -> None:
    """Reverse path: 0006 -> 0004 must remove idempotency_records + agent_signature cleanly."""
    _run_alembic(["upgrade", "head"], pg_url, repo_root)
    assert await _current_revision(pg_engine) == "0006_agent_signature"

    result = _run_alembic(["downgrade", "-2"], pg_url, repo_root)
    assert result.returncode == 0, f"downgrade failed: {result.stderr}"

    assert await _current_revision(pg_engine) == "0004_bundle_approval_workflow"
    assert not await _table_exists(pg_engine, "idempotency_records")
    assert not await _index_exists(pg_engine, "ix_idempotency_records_expires_at")
    # The 0004 objects must STILL be present.
    assert await _table_exists(pg_engine, "policy_bundle_approvals")


async def test_downgrade_three_drops_0004_objects(
    pg_engine: AsyncEngine, pg_url: str, repo_root
) -> None:
    """Reverse path: 0006 -> 0003 must remove every object 0004 + 0005 + 0006 created."""
    _run_alembic(["upgrade", "head"], pg_url, repo_root)
    assert await _current_revision(pg_engine) == "0006_agent_signature"

    result = _run_alembic(["downgrade", "-3"], pg_url, repo_root)
    assert result.returncode == 0, f"downgrade -3 failed: {result.stderr}"

    assert await _current_revision(pg_engine) == "0003_event_output"

    assert not await _table_exists(pg_engine, "idempotency_records")
    assert not await _table_exists(pg_engine, "policy_bundle_approvals")
    assert not await _index_exists(pg_engine, "uq_policy_bundles_one_active_per_tenant")
    assert not await _trigger_exists(pg_engine, "trg_policy_bundle_approvals_block_update")
    assert not await _trigger_exists(pg_engine, "trg_policy_bundle_approvals_block_delete")


async def test_upgrade_after_downgrade_round_trip(
    pg_engine: AsyncEngine, pg_url: str, repo_root
) -> None:
    """Full round-trip: head -> head-3 -> head must finish at head with full schema.

    Catches the subtle migration bug where downgrade leaves orphan state
    (sequence, type, function) that prevents a clean re-upgrade.
    """
    _run_alembic(["upgrade", "head"], pg_url, repo_root)
    _run_alembic(["downgrade", "-3"], pg_url, repo_root)

    result = _run_alembic(["upgrade", "head"], pg_url, repo_root)
    assert result.returncode == 0, f"re-upgrade failed: {result.stderr}"

    assert await _current_revision(pg_engine) == "0006_agent_signature"
    assert await _table_exists(pg_engine, "policy_bundle_approvals")
    assert await _table_exists(pg_engine, "idempotency_records")
    assert await _index_exists(pg_engine, "uq_policy_bundles_one_active_per_tenant")
    assert await _trigger_exists(pg_engine, "trg_policy_bundle_approvals_block_update")
    assert await _trigger_exists(pg_engine, "trg_policy_bundle_approvals_block_delete")
    assert await _index_exists(pg_engine, "ix_idempotency_records_expires_at")
    # CP9.18 agent_signature column.
    async with pg_engine.connect() as conn:
        result_col = await conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'receipts' AND column_name = 'agent_signature'"
            )
        )
        assert result_col.first() is not None

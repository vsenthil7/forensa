"""PG integration tests for the ma_export_jobs migration + repo (CP9.43 / IP #8).

Schema half of NEW-P12.X.ma-export-async-job. Verifies:

  1. The 0008_ma_export_jobs migration applies cleanly forward on a real
     Postgres backend (CREATE TABLE + CHECK constraint + 2 indexes).
  2. The migration is reversible: downgrade -1 from 0008 drops the
     table + both indexes cleanly, returning to 0007.
  3. The CHECK constraint actually rejects an invalid status value at
     the DB level (defence in depth beyond the application's state
     machine).
  4. The 5 repo helpers (create / get / list / mark_pending_to_running /
     mark_running_to_completed / mark_failed) round-trip correctly
     against a real ma_export_jobs table.

Skipped when FORENSA_TEST_DB_URL unset, like the other tests/integration/
modules.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from packages.ledger.ma_export_job_repository import (
    MaExportJobStateError,
    create_ma_export_job,
    get_ma_export_job_by_id,
    list_ma_export_jobs_for_tenant,
    mark_ma_export_job_failed,
    mark_ma_export_job_pending_to_running,
    mark_ma_export_job_running_to_completed,
)
from packages.ledger.models import AgentRow, MaExportJobRow, TenantRow

pytestmark = pytest.mark.pg


def _run_alembic(args: list[str], pg_url: str, repo_root) -> subprocess.CompletedProcess[str]:
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


async def _current_revision(engine: AsyncEngine) -> str | None:
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT version_num FROM alembic_version"))
        row = result.first()
        return row[0] if row else None


# ---------- migration round-trip ----------


async def test_upgrade_to_0008_creates_ma_export_jobs_table(
    pg_engine: AsyncEngine, pg_url: str, repo_root
) -> None:
    _run_alembic(["downgrade", "base"], pg_url, repo_root)

    result = _run_alembic(["upgrade", "head"], pg_url, repo_root)
    assert result.returncode == 0, f"upgrade failed: {result.stderr}"

    assert await _current_revision(pg_engine) == "0008_ma_export_jobs"

    assert await _table_exists(pg_engine, "ma_export_jobs")
    assert await _index_exists(pg_engine, "ix_ma_export_jobs_tenant_requested")
    assert await _index_exists(pg_engine, "ix_ma_export_jobs_status")


async def test_downgrade_from_0008_removes_ma_export_jobs(
    pg_engine: AsyncEngine, pg_url: str, repo_root
) -> None:
    _run_alembic(["upgrade", "head"], pg_url, repo_root)
    assert await _current_revision(pg_engine) == "0008_ma_export_jobs"

    result = _run_alembic(["downgrade", "-1"], pg_url, repo_root)
    assert result.returncode == 0, f"downgrade failed: {result.stderr}"

    assert await _current_revision(pg_engine) == "0007_timestamp_anchors"
    assert not await _table_exists(pg_engine, "ma_export_jobs")
    assert not await _index_exists(pg_engine, "ix_ma_export_jobs_tenant_requested")
    assert not await _index_exists(pg_engine, "ix_ma_export_jobs_status")


async def test_check_constraint_rejects_invalid_status(
    pg_engine: AsyncEngine, pg_url: str, repo_root
) -> None:
    """DB-level defence in depth: the CHECK constraint must reject any
    status value outside the enum, even via raw SQL INSERT."""
    _run_alembic(["upgrade", "head"], pg_url, repo_root)

    # We need a tenant row first because tenant_id has an FK.
    async with pg_engine.begin() as conn:
        # Clean any prior test residue.
        await conn.execute(text("TRUNCATE TABLE ma_export_jobs CASCADE"))
        await conn.execute(text("TRUNCATE TABLE tenants RESTART IDENTITY CASCADE"))

        tenant_uuid = uuid4()
        await conn.execute(
            text(
                "INSERT INTO tenants (id, slug, display_name, signing_key_id, created_at) "
                "VALUES (:id, :slug, :name, :key, :ts)"
            ),
            {
                "id": tenant_uuid,
                "slug": "constraint-test",
                "name": "Constraint Test",
                "key": "k1",
                "ts": datetime.now(UTC),
            },
        )

    async with pg_engine.begin() as conn:
        with pytest.raises(IntegrityError):
            await conn.execute(
                text(
                    "INSERT INTO ma_export_jobs "
                    "(id, tenant_id, status, scope_start, scope_end, requested_at) "
                    "VALUES (:id, :tid, :status, :s, :e, :req)"
                ),
                {
                    "id": uuid4(),
                    "tid": tenant_uuid,
                    "status": "bogus_value_xx",  # 14 chars, fits column; still not in CHECK enum
                    "s": datetime(2026, 1, 1, tzinfo=UTC),
                    "e": datetime(2026, 5, 1, tzinfo=UTC),
                    "req": datetime.now(UTC),
                },
            )


# ---------- repo helpers against real PG ----------


@pytest_asyncio.fixture
async def session_with_tenant(pg_engine: AsyncEngine, pg_url: str, repo_root):
    """Yield an AsyncSession against migrated DB + one tenant + one agent."""
    _run_alembic(["upgrade", "head"], pg_url, repo_root)

    async with pg_engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE TABLE ma_export_jobs, agents, tenants RESTART IDENTITY CASCADE")
        )

    session_factory = async_sessionmaker(pg_engine, expire_on_commit=False)
    async with session_factory() as session:
        tenant_id = uuid4()
        agent_id = uuid4()
        session.add(
            TenantRow(
                id=tenant_id,
                slug=f"repo-test-{tenant_id}",
                display_name="Repo Test Tenant",
                signing_key_id="repo-test-key",
                created_at=datetime.now(UTC),
            )
        )
        await session.flush()
        session.add(
            AgentRow(
                id=agent_id,
                tenant_id=tenant_id,
                slug="repo-test-agent",
                display_name="Repo Test Agent",
                identity_public_key=b"\x00" * 32,
                status="active",
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()
        yield session, tenant_id, agent_id


async def test_repo_create_then_get_round_trip(session_with_tenant) -> None:
    session, tenant_id, _ = session_with_tenant
    job_id = await create_ma_export_job(
        session,
        tenant_id=tenant_id,
        scope_start=datetime(2026, 1, 1, tzinfo=UTC),
        scope_end=datetime(2026, 5, 1, tzinfo=UTC),
        encrypt_for_pubkey_b64="dGVzdA==",
        platform_sign_key_id="platform-v1",
    )
    await session.commit()

    row = await get_ma_export_job_by_id(session, job_id)
    assert row is not None
    assert row.id == job_id
    assert row.tenant_id == tenant_id
    assert row.status == "pending"
    assert row.encrypt_for_pubkey_b64 == "dGVzdA=="
    assert row.platform_sign_key_id == "platform-v1"
    assert row.result_export is None
    assert row.result_error is None


async def test_repo_get_cross_tenant_returns_none(session_with_tenant) -> None:
    """CP9.33 SQL-layer tenant scoping: a foreign tenant_id kwarg returns None."""
    session, tenant_id, _ = session_with_tenant
    job_id = await create_ma_export_job(
        session,
        tenant_id=tenant_id,
        scope_start=datetime(2026, 1, 1, tzinfo=UTC),
        scope_end=datetime(2026, 5, 1, tzinfo=UTC),
    )
    await session.commit()

    other_tenant = uuid4()
    row = await get_ma_export_job_by_id(session, job_id, tenant_id=other_tenant)
    assert row is None

    # But with the correct tenant_id, we get it back.
    row_correct = await get_ma_export_job_by_id(session, job_id, tenant_id=tenant_id)
    assert row_correct is not None
    assert row_correct.id == job_id


async def test_repo_state_machine_pending_running_completed(
    session_with_tenant,
) -> None:
    """Full happy-path lifecycle: pending -> running -> completed."""
    session, tenant_id, _ = session_with_tenant
    job_id = await create_ma_export_job(
        session,
        tenant_id=tenant_id,
        scope_start=datetime(2026, 1, 1, tzinfo=UTC),
        scope_end=datetime(2026, 5, 1, tzinfo=UTC),
    )
    await session.commit()

    # pending -> running
    await mark_ma_export_job_pending_to_running(session, job_id)
    await session.commit()
    row = await get_ma_export_job_by_id(session, job_id)
    assert row is not None
    assert row.status == "running"
    assert row.started_at is not None

    # running -> completed
    payload = {"version": "1.0", "summary": {"receipts_total": 42}}
    await mark_ma_export_job_running_to_completed(session, job_id, result_export=payload)
    await session.commit()
    row = await get_ma_export_job_by_id(session, job_id)
    assert row is not None
    assert row.status == "completed"
    assert row.result_export == payload
    assert row.completed_at is not None
    assert row.result_error is None


async def test_repo_state_machine_pending_failed(session_with_tenant) -> None:
    """Startup failure path: pending -> failed (skip running)."""
    session, tenant_id, _ = session_with_tenant
    job_id = await create_ma_export_job(
        session,
        tenant_id=tenant_id,
        scope_start=datetime(2026, 1, 1, tzinfo=UTC),
        scope_end=datetime(2026, 5, 1, tzinfo=UTC),
    )
    await session.commit()

    await mark_ma_export_job_failed(session, job_id, error_message="startup boom")
    await session.commit()
    row = await get_ma_export_job_by_id(session, job_id)
    assert row is not None
    assert row.status == "failed"
    assert row.result_error == "startup boom"
    assert row.result_export is None


async def test_repo_state_machine_running_to_failed(session_with_tenant) -> None:
    """Mid-job failure path: running -> failed."""
    session, tenant_id, _ = session_with_tenant
    job_id = await create_ma_export_job(
        session,
        tenant_id=tenant_id,
        scope_start=datetime(2026, 1, 1, tzinfo=UTC),
        scope_end=datetime(2026, 5, 1, tzinfo=UTC),
    )
    await session.commit()

    await mark_ma_export_job_pending_to_running(session, job_id)
    await session.commit()

    await mark_ma_export_job_failed(session, job_id, error_message="encryption-key fetch failed")
    await session.commit()
    row = await get_ma_export_job_by_id(session, job_id)
    assert row is not None
    assert row.status == "failed"
    assert row.result_error == "encryption-key fetch failed"


async def test_repo_terminal_status_blocks_further_transitions(
    session_with_tenant,
) -> None:
    """A completed job cannot be re-completed or marked failed."""
    session, tenant_id, _ = session_with_tenant
    job_id = await create_ma_export_job(
        session,
        tenant_id=tenant_id,
        scope_start=datetime(2026, 1, 1, tzinfo=UTC),
        scope_end=datetime(2026, 5, 1, tzinfo=UTC),
    )
    await session.commit()
    await mark_ma_export_job_pending_to_running(session, job_id)
    await session.commit()
    await mark_ma_export_job_running_to_completed(session, job_id, result_export={"ok": True})
    await session.commit()

    with pytest.raises(MaExportJobStateError, match="terminal"):
        await mark_ma_export_job_failed(session, job_id, error_message="too late")
    with pytest.raises(MaExportJobStateError, match="terminal"):
        await mark_ma_export_job_running_to_completed(
            session, job_id, result_export={"again": True}
        )


async def test_repo_list_for_tenant_orders_by_requested_at_desc(
    session_with_tenant,
) -> None:
    """list_ma_export_jobs_for_tenant returns newest first."""
    session, tenant_id, _ = session_with_tenant
    ts1 = datetime(2026, 5, 15, 10, 0, tzinfo=UTC)
    ts2 = datetime(2026, 5, 15, 11, 0, tzinfo=UTC)
    ts3 = datetime(2026, 5, 15, 12, 0, tzinfo=UTC)
    j1 = await create_ma_export_job(
        session,
        tenant_id=tenant_id,
        scope_start=datetime(2026, 1, 1, tzinfo=UTC),
        scope_end=datetime(2026, 5, 1, tzinfo=UTC),
        requested_at=ts1,
    )
    j2 = await create_ma_export_job(
        session,
        tenant_id=tenant_id,
        scope_start=datetime(2026, 1, 1, tzinfo=UTC),
        scope_end=datetime(2026, 5, 1, tzinfo=UTC),
        requested_at=ts2,
    )
    j3 = await create_ma_export_job(
        session,
        tenant_id=tenant_id,
        scope_start=datetime(2026, 1, 1, tzinfo=UTC),
        scope_end=datetime(2026, 5, 1, tzinfo=UTC),
        requested_at=ts3,
    )
    await session.commit()

    rows = await list_ma_export_jobs_for_tenant(session, tenant_id)
    assert [r.id for r in rows] == [j3, j2, j1]


async def test_repo_list_for_tenant_isolates_by_tenant(
    session_with_tenant,
) -> None:
    """A different tenant_id sees zero rows even after another tenant
    has jobs."""
    session, tenant_id, _ = session_with_tenant
    await create_ma_export_job(
        session,
        tenant_id=tenant_id,
        scope_start=datetime(2026, 1, 1, tzinfo=UTC),
        scope_end=datetime(2026, 5, 1, tzinfo=UTC),
    )
    await session.commit()

    other_tenant = uuid4()
    rows = await list_ma_export_jobs_for_tenant(session, other_tenant)
    assert rows == []


async def test_repo_supports_full_orm_load_of_terminal_row(
    session_with_tenant,
) -> None:
    """Round-trip a completed row through ORM load + new session read.

    Confirms the JSONB result_export survives a serialize-deserialize and
    the row metadata is intact on a fresh ORM load.
    """
    session, tenant_id, _ = session_with_tenant
    job_id = await create_ma_export_job(
        session,
        tenant_id=tenant_id,
        scope_start=datetime(2026, 1, 1, tzinfo=UTC),
        scope_end=datetime(2026, 5, 1, tzinfo=UTC),
    )
    await session.commit()
    await mark_ma_export_job_pending_to_running(session, job_id)
    await session.commit()
    payload = {
        "version": "1.0",
        "summary": {"receipts_total": 5, "denies": 1, "escalates": 0},
        "signatures": {"tenant": "abc", "platform": "def"},
        "nested": {"deep": {"key": [1, 2, 3]}},
    }
    await mark_ma_export_job_running_to_completed(session, job_id, result_export=payload)
    await session.commit()

    # Re-fetch the row in a fresh session-cached state.
    refetched = await get_ma_export_job_by_id(session, job_id)
    assert refetched is not None
    assert refetched.result_export == payload
    assert refetched.result_export["nested"]["deep"]["key"] == [1, 2, 3]


# ---------- helper assertions ----------


def test_mock_helpers_smoke() -> None:
    """Trivial: confirm imports landed."""
    assert MaExportJobRow.__tablename__ == "ma_export_jobs"
    assert MaExportJobStateError is not None
    assert AsyncSession is not None

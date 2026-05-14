"""Partial UNIQUE index ``uq_policy_bundles_one_active_per_tenant`` (real Postgres).

Closes NEW-P9.15.partial-unique-test-on-pg from CP9.15.1's honest-gaps list.

SQLite ignores ``postgresql_where`` clauses on indexes, so under the default
unit-test backend the partial UNIQUE behaves like a no-op. These tests run
only against real Postgres and assert that:

- Two ``active`` bundles for the same tenant cannot coexist (sequential).
- Concurrent activations from two sessions race-safely: exactly one wins,
  the other receives ``IntegrityError`` from the unique violation.
- The constraint is tenant-scoped (two tenants can each have one active).
- ``superseded`` and other non-active statuses are not constrained by the
  partial index, so the workflow's supersede-then-activate transition can
  flip an old active to superseded and a new bundle to active inside the
  same transaction without the index seeing two actives mid-flush.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

pytestmark = pytest.mark.pg


async def _insert_tenant(session: AsyncSession, name: str = "Partial UQ Tenant") -> uuid.UUID:
    tenant_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO tenants (id, slug, display_name, signing_key_id, created_at) "
            "VALUES (:id, :slug, :name, :kid, :now)"
        ),
        {
            "id": tenant_id,
            "slug": f"t-{tenant_id.hex[:8]}",
            "name": name,
            "kid": f"kid-{tenant_id.hex[:8]}",
            "now": datetime.now(UTC),
        },
    )
    return tenant_id


async def _insert_bundle(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    version: str,
    status: str,
) -> uuid.UUID:
    bundle_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO policy_bundles "
            "(id, tenant_id, version, content_hash, content, created_at, status) "
            "VALUES (:id, :tid, :ver, :hash, '{}'::jsonb, :now, :status)"
        ),
        {
            "id": bundle_id,
            "tid": tenant_id,
            "ver": version,
            "hash": uuid.uuid4().hex + uuid.uuid4().hex,
            "now": datetime.now(UTC),
            "status": status,
        },
    )
    return bundle_id


async def test_two_actives_same_tenant_sequential_raises(
    pg_clean_session: AsyncSession,
) -> None:
    """Two bundles, same tenant, both active inserted one after the other = rejected."""
    tenant_id = await _insert_tenant(pg_clean_session)
    await _insert_bundle(pg_clean_session, tenant_id=tenant_id, version="1.0.0", status="active")
    await pg_clean_session.commit()

    with pytest.raises(IntegrityError) as excinfo:
        await _insert_bundle(
            pg_clean_session, tenant_id=tenant_id, version="2.0.0", status="active"
        )
        await pg_clean_session.commit()

    assert "uq_policy_bundles_one_active_per_tenant" in str(excinfo.value)


async def test_active_and_superseded_can_coexist(pg_clean_session: AsyncSession) -> None:
    """Partial index only constrains status='active'; superseded/proposed are unconstrained."""
    tenant_id = await _insert_tenant(pg_clean_session)
    await _insert_bundle(
        pg_clean_session, tenant_id=tenant_id, version="1.0.0", status="superseded"
    )
    await _insert_bundle(
        pg_clean_session, tenant_id=tenant_id, version="2.0.0", status="superseded"
    )
    await _insert_bundle(pg_clean_session, tenant_id=tenant_id, version="3.0.0", status="active")
    await pg_clean_session.commit()

    result = await pg_clean_session.execute(
        text(
            "SELECT status, COUNT(*) FROM policy_bundles "
            "WHERE tenant_id = :tid GROUP BY status ORDER BY status"
        ),
        {"tid": tenant_id},
    )
    counts = {row[0]: row[1] for row in result.all()}
    assert counts == {"active": 1, "superseded": 2}


async def test_actives_on_different_tenants_both_allowed(
    pg_clean_session: AsyncSession,
) -> None:
    """The partial UNIQUE is tenant-scoped, not global."""
    tenant_a = await _insert_tenant(pg_clean_session, name="A")
    tenant_b = await _insert_tenant(pg_clean_session, name="B")
    await _insert_bundle(pg_clean_session, tenant_id=tenant_a, version="1.0.0", status="active")
    await _insert_bundle(pg_clean_session, tenant_id=tenant_b, version="1.0.0", status="active")
    await pg_clean_session.commit()

    result = await pg_clean_session.execute(
        text("SELECT COUNT(*) FROM policy_bundles WHERE status = 'active'")
    )
    assert result.scalar_one() == 2


async def test_concurrent_activations_race_one_wins(pg_engine: AsyncEngine) -> None:
    """Two sessions racing to activate different bundles for the same tenant:
    exactly one must succeed, the other must hit IntegrityError.

    This is the test SQLite could never run because (a) it ignores the partial
    WHERE clause and (b) it has no real concurrency model. Even on Postgres,
    proving the race-safety needs two concurrent transactions; a single
    transaction cannot exercise the constraint at flush boundary the way two
    real sessions do.
    """
    factory = async_sessionmaker(pg_engine, expire_on_commit=False)

    # Set up: clean state and one tenant + two proposed bundles.
    async with pg_engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE policy_bundle_approvals, receipts, events, "
                "policy_snapshots, policy_bundles, agents, tenants "
                "RESTART IDENTITY CASCADE"
            )
        )
    async with factory() as setup:
        tenant_id = await _insert_tenant(setup, name="Race")
        bundle_a = await _insert_bundle(
            setup, tenant_id=tenant_id, version="1.0.0", status="proposed"
        )
        bundle_b = await _insert_bundle(
            setup, tenant_id=tenant_id, version="2.0.0", status="proposed"
        )
        await setup.commit()

    async def activate(bundle_id: uuid.UUID) -> str:
        """Activate one bundle in its own session; return 'ok' or 'conflict'."""
        try:
            async with factory() as session:
                # Hold a brief lock-window so both coroutines reach UPDATE in flight.
                await session.execute(text("SELECT pg_sleep(0.05)"))
                await session.execute(
                    text(
                        "UPDATE policy_bundles SET status = 'active' "
                        "WHERE id = :id AND status = 'proposed'"
                    ),
                    {"id": bundle_id},
                )
                await session.commit()
            return "ok"
        except IntegrityError as exc:
            assert "uq_policy_bundles_one_active_per_tenant" in str(exc), str(exc)
            return "conflict"

    results = await asyncio.gather(activate(bundle_a), activate(bundle_b))

    # Exactly one winner. Either order acceptable.
    assert sorted(results) == ["conflict", "ok"], f"expected exactly one winner; got {results!r}"

    # And on the DB, exactly one bundle is active.
    async with factory() as verify:
        result = await verify.execute(
            text("SELECT COUNT(*) FROM policy_bundles WHERE status = 'active'")
        )
        assert result.scalar_one() == 1


async def test_supersede_then_activate_in_same_transaction(
    pg_clean_session: AsyncSession,
) -> None:
    """The workflow's atomic flip (supersede old active + activate new) must work.

    Order matters: supersede the existing active FIRST, then activate the
    new bundle. Postgres's deferred-constraint behaviour and the partial
    index together must permit this within a single transaction.
    """
    tenant_id = await _insert_tenant(pg_clean_session)
    bundle_old = await _insert_bundle(
        pg_clean_session, tenant_id=tenant_id, version="1.0.0", status="active"
    )
    bundle_new = await _insert_bundle(
        pg_clean_session, tenant_id=tenant_id, version="2.0.0", status="approved"
    )
    await pg_clean_session.commit()

    # The workflow's transactional flip:
    await pg_clean_session.execute(
        text("UPDATE policy_bundles SET status = 'superseded' WHERE id = :id"),
        {"id": bundle_old},
    )
    await pg_clean_session.execute(
        text("UPDATE policy_bundles SET status = 'active' WHERE id = :id"),
        {"id": bundle_new},
    )
    await pg_clean_session.commit()

    result = await pg_clean_session.execute(
        text("SELECT id FROM policy_bundles " "WHERE tenant_id = :tid AND status = 'active'"),
        {"tid": tenant_id},
    )
    rows = result.all()
    assert len(rows) == 1
    assert rows[0][0] == bundle_new

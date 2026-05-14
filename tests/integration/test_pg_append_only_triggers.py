"""Append-only triggers on policy_bundle_approvals (real Postgres).

Closes the trigger-verification half of CP9.15.1 (which claimed the triggers
work but only verified them via ``alembic upgrade --sql`` preview, not via
actually attempting forbidden mutations against a live DB).

What this verifies that the offline SQL preview cannot:

- The PL/pgSQL function ``forensa_block_approval_mutation`` is installed.
- The BEFORE UPDATE trigger fires and aborts the transaction with the
  expected message.
- The BEFORE DELETE trigger fires and aborts the transaction with the
  expected message.
- INSERT continues to work (so the append-only ledger remains writable).
- The triggers are tenant-blind: any UPDATE or DELETE is blocked, regardless
  of whose row it targets. Defence-in-depth against a compromised
  per-tenant connection.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.pg


_EXPECTED_MSG = "policy_bundle_approvals is append-only"


async def _seed_tenant_bundle_and_approval(
    session: AsyncSession,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Insert tenant + bundle + one approval row. Returns the three IDs."""
    tenant_id = uuid.uuid4()
    bundle_id = uuid.uuid4()
    approval_id = uuid.uuid4()
    now = datetime.now(UTC)

    await session.execute(
        text(
            "INSERT INTO tenants (id, slug, display_name, signing_key_id, created_at) "
            "VALUES (:id, :slug, :name, :kid, :now)"
        ),
        {
            "id": tenant_id,
            "slug": f"t-{tenant_id.hex[:8]}",
            "name": "Trigger Test Tenant",
            "kid": "kid-trigger-test",
            "now": now,
        },
    )
    await session.execute(
        text(
            "INSERT INTO policy_bundles "
            "(id, tenant_id, version, content_hash, content, created_at, status) "
            "VALUES (:id, :tid, '1.0.0', :hash, '{}'::jsonb, :now, 'proposed')"
        ),
        {"id": bundle_id, "tid": tenant_id, "hash": "h" * 64, "now": now},
    )
    await session.execute(
        text(
            "INSERT INTO policy_bundle_approvals "
            "(id, bundle_id, tenant_id, from_status, to_status, "
            "actor_id, actor_role, reason, decided_at) "
            "VALUES (:id, :bid, :tid, 'proposed', 'reviewed', "
            ":aid, 'reviewer', :reason, :now)"
        ),
        {
            "id": approval_id,
            "bid": bundle_id,
            "tid": tenant_id,
            "aid": uuid.uuid4(),
            "reason": "looks good",
            "now": now,
        },
    )
    await session.commit()
    return tenant_id, bundle_id, approval_id


async def test_insert_into_approvals_is_permitted(pg_clean_session: AsyncSession) -> None:
    """Append (INSERT) continues to work; the trigger only blocks UPDATE/DELETE."""
    _, _, approval_id = await _seed_tenant_bundle_and_approval(pg_clean_session)

    result = await pg_clean_session.execute(
        text("SELECT COUNT(*) FROM policy_bundle_approvals WHERE id = :id"),
        {"id": approval_id},
    )
    assert result.scalar_one() == 1


async def test_update_to_approval_row_raises_via_trigger(
    pg_clean_session: AsyncSession,
) -> None:
    """UPDATE on any column of an approval row must abort with the trigger message.

    This is the verification the CP9.15.1 commit message implied was done
    but actually wasn't (the trigger SQL existed only in the alembic preview).
    """
    _, _, approval_id = await _seed_tenant_bundle_and_approval(pg_clean_session)

    with pytest.raises(DBAPIError) as excinfo:
        await pg_clean_session.execute(
            text("UPDATE policy_bundle_approvals SET reason = :r WHERE id = :id"),
            {"r": "tampered", "id": approval_id},
        )
        await pg_clean_session.commit()

    assert _EXPECTED_MSG in str(
        excinfo.value
    ), f"trigger fired but message mismatch: {excinfo.value!r}"


async def test_delete_of_approval_row_raises_via_trigger(
    pg_clean_session: AsyncSession,
) -> None:
    """DELETE on any approval row must abort with the trigger message."""
    _, _, approval_id = await _seed_tenant_bundle_and_approval(pg_clean_session)

    with pytest.raises(DBAPIError) as excinfo:
        await pg_clean_session.execute(
            text("DELETE FROM policy_bundle_approvals WHERE id = :id"),
            {"id": approval_id},
        )
        await pg_clean_session.commit()

    assert _EXPECTED_MSG in str(
        excinfo.value
    ), f"trigger fired but message mismatch: {excinfo.value!r}"


async def test_trigger_function_exists_in_pg_catalog(pg_clean_session: AsyncSession) -> None:
    """The PL/pgSQL function is loaded under the expected name.

    Belt + braces: even if a future migration changed trigger targeting,
    the function itself must remain.
    """
    result = await pg_clean_session.execute(
        text("SELECT 1 FROM pg_proc WHERE proname = 'forensa_block_approval_mutation'")
    )
    assert result.scalar() == 1


async def test_bulk_update_attempt_also_blocked(pg_clean_session: AsyncSession) -> None:
    """Trigger is FOR EACH ROW; a multi-row UPDATE must still abort on the first row.

    Catches the bug-class where someone weakens the trigger to FOR EACH
    STATEMENT thinking it's an optimisation.
    """
    await _seed_tenant_bundle_and_approval(pg_clean_session)
    await _seed_tenant_bundle_and_approval(pg_clean_session)

    with pytest.raises(DBAPIError) as excinfo:
        await pg_clean_session.execute(
            text("UPDATE policy_bundle_approvals SET reason = 'mass tamper'")
        )
        await pg_clean_session.commit()

    assert _EXPECTED_MSG in str(excinfo.value)


async def test_bulk_delete_attempt_also_blocked(pg_clean_session: AsyncSession) -> None:
    """DELETE without WHERE must also be blocked by the trigger."""
    await _seed_tenant_bundle_and_approval(pg_clean_session)
    await _seed_tenant_bundle_and_approval(pg_clean_session)

    with pytest.raises(DBAPIError) as excinfo:
        await pg_clean_session.execute(text("DELETE FROM policy_bundle_approvals"))
        await pg_clean_session.commit()

    assert _EXPECTED_MSG in str(excinfo.value)

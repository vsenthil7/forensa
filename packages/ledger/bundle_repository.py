"""Policy bundle repository (CP9.14 / NEW-P9.8.24).

Closes the second half of BR-04: snapshot binding was done in CP6.x, but the
``PolicyBundleRow`` ORM had no repository - bundles existed only as in-memory
``PolicyBundle`` Pydantic models built by ``bundle_builder.build_bundle``.
This module is the missing persistence layer:

- ``write_bundle`` -> INSERT a new bundle
- ``get_active_bundle_for_tenant`` -> latest by ``created_at DESC`` (today's
  notion of "active" until the change-management workflow tracked in
  ``NEW-P9.8.X.bundle-approval-workflow`` lands)
- ``get_bundle_by_id`` -> single-row lookup
- ``list_bundles_for_tenant`` -> chronological list for audit / approval UI

Pure persistence: no validation beyond what the ORM unique constraints
enforce ((tenant_id, version) unique). The caller's ``session_scope``
controls the transaction.

This module unlocks production wiring for the ``PolicyBundleProvider`` in
``apps.api.ingest_service`` - see ``PostgresBundleProvider`` there.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.ledger.models import PolicyBundleRow
from packages.schema.policy_bundle import PolicyBundle


async def write_bundle(session: AsyncSession, bundle: PolicyBundle) -> UUID:
    """Persist a new ``PolicyBundle`` and return its id.

    Adds the row to the session and flushes. The caller's session_scope
    controls commit. The ``(tenant_id, version)`` UNIQUE constraint on the
    table will surface as an ``IntegrityError`` on duplicate version
    submission - callers wishing to upsert should call
    ``get_active_bundle_for_tenant`` first and skip the write if the
    content_hash matches.

    CP9.15: explicitly sets ``status='proposed'`` on the new row. The ORM
    column carries this as a default for DB-level INSERTs but the in-memory
    instance needs the value set explicitly so the bundle approval workflow
    can read it before any DB flush actually happens.
    """
    row = PolicyBundleRow(
        id=bundle.id,
        tenant_id=bundle.tenant_id,
        version=bundle.version,
        content_hash=bundle.content_hash,
        content=bundle.content,
        created_at=bundle.created_at,
        status="proposed",
    )
    session.add(row)
    await session.flush()
    return bundle.id


async def get_bundle_by_id(
    session: AsyncSession,
    bundle_id: UUID,
) -> PolicyBundle | None:
    """Return the ``PolicyBundle`` with this id, or ``None`` if not found.

    Used by the snapshot replay path to verify a Receipt's
    ``policy_bundle_id`` resolves to a real (and consistent) bundle - the
    snapshot's ``content_hash`` must equal the bundle's ``content_hash`` for
    a clean replay. Drift between them is the
    ``PolicyBundleHashMismatchError`` case.
    """
    stmt = select(PolicyBundleRow).where(PolicyBundleRow.id == bundle_id).limit(1)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return _row_to_bundle(row)


async def get_active_bundle_for_tenant(
    session: AsyncSession,
    tenant_id: UUID,
) -> PolicyBundle | None:
    """Return the bundle currently in ``status='active'`` for the tenant, or ``None``.

    CP9.15 / NEW-P9.8.X.bundle-approval-workflow: this function now filters
    on ``status = 'active'`` rather than returning the most recently created
    bundle regardless of status. The DB ``uq_policy_bundles_one_active_per_tenant``
    partial UNIQUE index guarantees at most one row matches, so the query
    returns 0 or 1 row.

    Returns ``None`` if the tenant has no active bundle - which is the
    expected state for a brand-new tenant, OR for a tenant whose bundles
    are all still pending in the approval workflow. The ``PostgresBundleProvider``
    cache-miss bootstrap path handles both cases by building and persisting
    a default bundle (in ``proposed`` status today; callers must then walk
    it through ``review`` / ``approve`` / ``activate`` for it to actually
    become active).

    Pre-CP9.15 behaviour (latest by ``created_at`` regardless of status) is
    preserved by callers passing through ``list_bundles_for_tenant`` and
    filtering / sorting client-side.
    """
    stmt = (
        select(PolicyBundleRow)
        .where(
            PolicyBundleRow.tenant_id == tenant_id,
            PolicyBundleRow.status == "active",
        )
        .order_by(PolicyBundleRow.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return _row_to_bundle(row)


async def list_bundles_for_tenant(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    limit: int = 50,
) -> list[PolicyBundle]:
    """Return up to ``limit`` ``PolicyBundle`` rows for the tenant, newest first.

    For the future audit / approval UI. Newest-first ordering is by
    ``created_at DESC``; the ``(tenant_id,)`` index makes the scan cheap.
    """
    stmt = (
        select(PolicyBundleRow)
        .where(PolicyBundleRow.tenant_id == tenant_id)
        .order_by(PolicyBundleRow.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [_row_to_bundle(row) for row in rows]


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _row_to_bundle(row: PolicyBundleRow) -> PolicyBundle:
    """Reconstruct a ``PolicyBundle`` from an ORM row."""
    return PolicyBundle(
        id=row.id,
        tenant_id=row.tenant_id,
        version=row.version,
        content_hash=row.content_hash,
        content=row.content,
        created_at=row.created_at,
    )

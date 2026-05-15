"""Repository helpers for the ``ma_export_jobs`` table (CP9.43 / IP #8).

Forward-only state machine enforcement at the application layer:

    pending -> running -> completed
                      \\-> failed
    pending -> failed   (startup failure)

Any other transition raises MaExportJobStateError. The DB has the
``ck_ma_export_jobs_status`` CHECK constraint as defence in depth so a
malformed SQL writer can't slip an invalid enum past us; the
application layer catches WRONG transitions (e.g. completed -> running)
which the CHECK can't.

Tenant scoping is enforced at SQL layer in every read helper (CP9.33
pattern). Cross-tenant reads return None at row level.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.ledger.models import MaExportJobRow

__all__ = [
    "JOB_STATUSES",
    "JOB_TERMINAL_STATUSES",
    "MaExportJobStateError",
    "create_ma_export_job",
    "get_ma_export_job_by_id",
    "list_ma_export_jobs_for_tenant",
    "mark_ma_export_job_failed",
    "mark_ma_export_job_pending_to_running",
    "mark_ma_export_job_running_to_completed",
]

JOB_STATUSES = ("pending", "running", "completed", "failed")
JOB_TERMINAL_STATUSES = ("completed", "failed")


class MaExportJobStateError(ValueError):
    """Raised on an invalid state transition or operation on a terminal job."""


async def create_ma_export_job(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    scope_start: datetime,
    scope_end: datetime,
    encrypt_for_pubkey_b64: str | None = None,
    platform_sign_key_id: str | None = None,
    requested_by_agent_id: UUID | None = None,
    requested_at: datetime | None = None,
) -> UUID:
    """Insert a new ma_export_jobs row in ``status='pending'``. Returns its id.

    Caller owns the transaction. The flush happens here so the caller
    can immediately query by id.
    """
    # tzinfo check must come FIRST: comparing a naive and aware datetime
    # raises TypeError in Python 3, so we can't even evaluate the < below
    # if either side is naive.
    if scope_start.tzinfo is None or scope_end.tzinfo is None:
        raise MaExportJobStateError("scope_start and scope_end must be timezone-aware")
    if scope_end < scope_start:
        raise MaExportJobStateError(
            f"scope_end ({scope_end}) must be >= scope_start ({scope_start})"
        )

    job_id = uuid4()
    row = MaExportJobRow(
        id=job_id,
        tenant_id=tenant_id,
        requested_by_agent_id=requested_by_agent_id,
        status="pending",
        scope_start=scope_start,
        scope_end=scope_end,
        encrypt_for_pubkey_b64=encrypt_for_pubkey_b64,
        platform_sign_key_id=platform_sign_key_id,
        requested_at=requested_at if requested_at is not None else datetime.now(UTC),
        started_at=None,
        completed_at=None,
        result_export=None,
        result_error=None,
    )
    session.add(row)
    await session.flush()
    return job_id


async def get_ma_export_job_by_id(
    session: AsyncSession,
    job_id: UUID,
    *,
    tenant_id: UUID | None = None,
) -> MaExportJobRow | None:
    """Fetch a job row by id, optionally tenant-scoped (CP9.33 pattern).

    When ``tenant_id`` is provided, the SQL gains ``AND tenant_id = :tid``
    so a cross-tenant probe returns None at the row level rather than
    leaking job existence.
    """
    stmt = select(MaExportJobRow).where(MaExportJobRow.id == job_id)
    if tenant_id is not None:
        stmt = stmt.where(MaExportJobRow.tenant_id == tenant_id)
    stmt = stmt.limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_ma_export_jobs_for_tenant(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[MaExportJobRow]:
    """List jobs for a tenant ordered by requested_at DESC (newest first).

    Powered by ix_ma_export_jobs_tenant_requested. For very deep pagination
    (>10K jobs) prefer cursor-based pagination in a future CP.
    """
    stmt = (
        select(MaExportJobRow)
        .where(MaExportJobRow.tenant_id == tenant_id)
        .order_by(MaExportJobRow.requested_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def mark_ma_export_job_pending_to_running(
    session: AsyncSession, job_id: UUID, *, started_at: datetime | None = None
) -> None:
    """Transition pending -> running. Raises if current status is not pending."""
    row = await get_ma_export_job_by_id(session, job_id)
    if row is None:
        raise MaExportJobStateError(f"job {job_id} not found")
    if row.status != "pending":
        raise MaExportJobStateError(
            f"cannot transition pending -> running from status {row.status!r}"
        )
    row.status = "running"
    row.started_at = started_at if started_at is not None else datetime.now(UTC)
    await session.flush()


async def mark_ma_export_job_running_to_completed(
    session: AsyncSession,
    job_id: UUID,
    *,
    result_export: dict[str, Any],
    completed_at: datetime | None = None,
) -> None:
    """Transition running -> completed with result payload.

    Raises if the row is already in a terminal status or if running -> X
    is being skipped.
    """
    row = await get_ma_export_job_by_id(session, job_id)
    if row is None:
        raise MaExportJobStateError(f"job {job_id} not found")
    if row.status in JOB_TERMINAL_STATUSES:
        raise MaExportJobStateError(
            f"cannot mark completed: job {job_id} is already in terminal status {row.status!r}"
        )
    if row.status != "running":
        raise MaExportJobStateError(
            f"cannot transition running -> completed from status {row.status!r}"
        )
    row.status = "completed"
    row.result_export = result_export
    row.completed_at = completed_at if completed_at is not None else datetime.now(UTC)
    await session.flush()


async def mark_ma_export_job_failed(
    session: AsyncSession,
    job_id: UUID,
    *,
    error_message: str,
    completed_at: datetime | None = None,
) -> None:
    """Transition any non-terminal status -> failed.

    Allowed from ``pending`` (startup failure) or ``running`` (mid-job
    failure). Raises if the row is already in a terminal status.

    ``error_message`` is truncated to 2048 chars to fit the DB column.
    """
    row = await get_ma_export_job_by_id(session, job_id)
    if row is None:
        raise MaExportJobStateError(f"job {job_id} not found")
    if row.status in JOB_TERMINAL_STATUSES:
        raise MaExportJobStateError(
            f"cannot mark failed: job {job_id} is already in terminal status {row.status!r}"
        )
    row.status = "failed"
    row.result_error = error_message[:2048]
    row.completed_at = completed_at if completed_at is not None else datetime.now(UTC)
    await session.flush()

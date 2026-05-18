"""GET /v1/metrics - tenant-scoped operational metrics snapshot (CP9.59 / API-F15).

A point-in-time JSON snapshot of operational health computed at request time
from the canonical DB tables. Closes Gap 14 in TRACEABILITY_MATRIX_LIVE.md
(``/status`` page placeholders).

**Scope choice (deliberately minimal):**

- JSON snapshot, NOT Prometheus text format. We can layer
  ``prometheus_client`` on top of this in CP10.x without breaking the
  consumer contract because this is the *UI* metrics surface.
- DB counts at request time. No in-memory counters, no histograms, no
  middleware. The trade-off: we cannot report request-latency histograms
  (which need middleware), so the response does NOT include signing
  latency p50/p95/p99. The ``/status`` console page accordingly does not
  show those panels.
- Tenant-scoped via ``principal.tenant_id``. Cross-tenant probes 403,
  matching the rest of the route patterns since CP9.18c.

**What the snapshot includes:**

- ``ingest``: total events for the tenant, events inside the rolling
  window, and events-per-hour rate (computed as
  ``events_in_window / window_hours``).
- ``signing``: total receipts for the tenant, receipts inside the
  window, receipts-per-hour rate, the latest receipt's ``sequence`` and
  ``signed_at`` timestamp (chain-head freshness proxy for chain
  integrity).
- ``anchoring``: count of TimestampAnchorRow rows in the window, split
  by ``status`` (anchored vs deferred). A non-zero ``deferred`` count
  is the canonical signal that FreeTSA was unreachable for that day's
  cron run.
- ``ma_export_jobs``: count by status (pending / running / completed /
  failed) over the same window. Useful for the diligence operator to
  see if any job is stuck.

The window defaults to 24 hours; callers can override with
``?window_hours=N`` (1 to 168 inclusive — one week).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import Principal, get_principal
from apps.api.routes.receipts import get_session
from packages.ledger.models import (
    EventRow,
    MaExportJobRow,
    ReceiptRow,
    TimestampAnchorRow,
)

router = APIRouter(prefix="/v1", tags=["metrics"])

_WINDOW_HOURS_MIN = 1
_WINDOW_HOURS_MAX = 168  # one week
_WINDOW_HOURS_DEFAULT = 24


class IngestMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events_total: int = Field(..., ge=0, description="Lifetime events for this tenant")
    events_in_window: int = Field(
        ..., ge=0, description="Events whose occurred_at falls inside the window"
    )
    events_per_hour: float = Field(
        ..., ge=0, description="events_in_window divided by window_hours"
    )


class SigningMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receipts_total: int = Field(..., ge=0)
    receipts_in_window: int = Field(..., ge=0)
    receipts_per_hour: float = Field(..., ge=0)
    chain_head_sequence: int | None = Field(
        None,
        description=(
            "Latest receipt's sequence number for this tenant. None if no"
            " receipts have ever been signed."
        ),
    )
    last_receipt_signed_at: datetime | None = Field(
        None, description="signed_at of the latest receipt; None if no receipts."
    )


class AnchoringMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anchors_in_window: int = Field(..., ge=0)
    anchored: int = Field(..., ge=0, description="status='anchored' count in window")
    deferred: int = Field(..., ge=0, description="status='deferred' count in window")


class MaJobMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pending: int = Field(..., ge=0)
    running: int = Field(..., ge=0)
    completed: int = Field(..., ge=0)
    failed: int = Field(..., ge=0)


class MetricsResponse(BaseModel):
    """Top-level metrics snapshot returned by GET /v1/metrics."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: UUID
    generated_at: datetime
    window_hours: int = Field(..., ge=_WINDOW_HOURS_MIN, le=_WINDOW_HOURS_MAX)
    window_start: datetime
    window_end: datetime
    ingest: IngestMetrics
    signing: SigningMetrics
    anchoring: AnchoringMetrics
    ma_export_jobs: MaJobMetrics


async def _count_scalar(session: AsyncSession, stmt) -> int:
    result = await session.execute(stmt)
    return int(result.scalar_one() or 0)


@router.get(
    "/metrics",
    status_code=status.HTTP_200_OK,
    response_model=MetricsResponse,
    summary="Operational metrics snapshot for the authenticated tenant (API-F15)",
    responses={
        401: {"description": "Authorization header missing or token invalid/expired"},
        403: {"description": "Principal's tenant_id does not match query tenant_id"},
        422: {"description": "window_hours out of range"},
    },
)
async def get_metrics(
    tenant_id: UUID = Query(  # noqa: B008
        ..., description="Tenant whose metrics to fetch; must match principal.tenant_id"
    ),
    window_hours: int = Query(  # noqa: B008
        _WINDOW_HOURS_DEFAULT,
        ge=_WINDOW_HOURS_MIN,
        le=_WINDOW_HOURS_MAX,
        description="Window length in hours; defaults to 24",
    ),
    principal: Principal = Depends(get_principal),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> MetricsResponse:
    """Return a tenant-scoped DB-snapshot of operational metrics.

    Authz: ``tenant_id`` MUST match ``principal.tenant_id`` (403 otherwise).
    """
    if tenant_id != principal.tenant_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "tenant_mismatch",
                "reason": "tenant_id query does not match authenticated principal.tenant_id",
            },
        )

    now = datetime.now(UTC)
    window_start = now - timedelta(hours=window_hours)

    # Ingest counts: events table
    events_total = await _count_scalar(
        session,
        select(func.count()).where(EventRow.tenant_id == tenant_id),
    )
    events_in_window = await _count_scalar(
        session,
        select(func.count()).where(
            EventRow.tenant_id == tenant_id,
            EventRow.occurred_at >= window_start,
            EventRow.occurred_at <= now,
        ),
    )

    # Signing counts: receipts table
    receipts_total = await _count_scalar(
        session,
        select(func.count()).where(ReceiptRow.tenant_id == tenant_id),
    )
    receipts_in_window = await _count_scalar(
        session,
        select(func.count()).where(
            ReceiptRow.tenant_id == tenant_id,
            ReceiptRow.signed_at >= window_start,
            ReceiptRow.signed_at <= now,
        ),
    )

    # Chain head: latest receipt for this tenant (sequence + signed_at)
    head_stmt = (
        select(ReceiptRow.sequence, ReceiptRow.signed_at)
        .where(ReceiptRow.tenant_id == tenant_id)
        .order_by(ReceiptRow.sequence.desc())
        .limit(1)
    )
    head_result = await session.execute(head_stmt)
    head_row = head_result.first()
    chain_head_sequence: int | None
    last_receipt_signed_at: datetime | None
    if head_row is None:
        chain_head_sequence = None
        last_receipt_signed_at = None
    else:
        chain_head_sequence = int(head_row[0])
        last_receipt_signed_at = head_row[1]

    # Anchoring counts: timestamp_anchors table, split by status
    anchored_in_window = await _count_scalar(
        session,
        select(func.count()).where(
            TimestampAnchorRow.tenant_id == tenant_id,
            TimestampAnchorRow.anchored_at >= window_start,
            TimestampAnchorRow.anchored_at <= now,
            TimestampAnchorRow.status == "anchored",
        ),
    )
    deferred_in_window = await _count_scalar(
        session,
        select(func.count()).where(
            TimestampAnchorRow.tenant_id == tenant_id,
            TimestampAnchorRow.anchored_at >= window_start,
            TimestampAnchorRow.anchored_at <= now,
            TimestampAnchorRow.status == "deferred",
        ),
    )

    # M&A diligence job counts by status (over window via requested_at)
    async def _job_count(status_str: str) -> int:
        return await _count_scalar(
            session,
            select(func.count()).where(
                MaExportJobRow.tenant_id == tenant_id,
                MaExportJobRow.requested_at >= window_start,
                MaExportJobRow.requested_at <= now,
                MaExportJobRow.status == status_str,
            ),
        )

    job_pending = await _job_count("pending")
    job_running = await _job_count("running")
    job_completed = await _job_count("completed")
    job_failed = await _job_count("failed")

    return MetricsResponse(
        tenant_id=tenant_id,
        generated_at=now,
        window_hours=window_hours,
        window_start=window_start,
        window_end=now,
        ingest=IngestMetrics(
            events_total=events_total,
            events_in_window=events_in_window,
            events_per_hour=round(events_in_window / window_hours, 4),
        ),
        signing=SigningMetrics(
            receipts_total=receipts_total,
            receipts_in_window=receipts_in_window,
            receipts_per_hour=round(receipts_in_window / window_hours, 4),
            chain_head_sequence=chain_head_sequence,
            last_receipt_signed_at=last_receipt_signed_at,
        ),
        anchoring=AnchoringMetrics(
            anchors_in_window=anchored_in_window + deferred_in_window,
            anchored=anchored_in_window,
            deferred=deferred_in_window,
        ),
        ma_export_jobs=MaJobMetrics(
            pending=job_pending,
            running=job_running,
            completed=job_completed,
            failed=job_failed,
        ),
    )

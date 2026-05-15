"""POST /v1/exports/ma-diligence - M&A due diligence bundle export (CP9.28 / BR-13).

An M&A acquirer or their forensic accountant requests the FULL evidence
trail for a target tenant over a multi-month window. This route composes
the bundle synchronously (today) by:

1. Listing every TimestampAnchorRow whose ``anchor_date`` falls in the
   requested window. The route refuses if the count exceeds
   ``_MAX_PACKS_PER_BUNDLE`` (today 366 = one year of daily anchors).
2. For each anchor, querying every Receipt for that day's [00:00, 23:59]
   slice via ``list_receipts_with_snapshot_for_tenant``.
3. Building one EvidencePack per anchored day with the anchor embedded
   inline so each pack is independently offline-verifiable.
4. Composing the resulting bundle via build_ma_diligence_export which
   binds a single ``ma_root_hash`` over the manifest header + every
   pack's root_hash + every anchor's anchor_id + every anchor's
   root_hash. Acquirer verifies the whole bundle in one operation.

Authz: same as evidence-pack route. The body's ``tenant_id`` MUST match
the authenticated principal's tenant_id. Cross-tenant access is 403.

Why POST not GET: M&A scope windows can be very wide (12-24 months);
the natural shape is a JSON request body. Also leaves room for future
filters (specific agent ids, specific event kinds) without query-string
explosion.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import Principal, get_principal
from apps.api.routes.receipts import get_session
from packages.export.builder import build_evidence_pack
from packages.export.ma_export import (
    MaDiligenceExport,
    MaExportError,
    build_ma_diligence_export,
)
from packages.export.schema import AnchorEvidence, EvidencePack
from packages.ledger.models import TimestampAnchorRow
from packages.ledger.repositories import list_receipts_with_snapshot_for_tenant

router = APIRouter(prefix="/v1/exports", tags=["exports"])

_MAX_PACKS_PER_BUNDLE = 366  # one year of daily anchored packs
_MAX_RECEIPTS_PER_PACK = 1000


class MaExportRequest(BaseModel):
    """Request body for the M&A export endpoint."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: UUID = Field(..., description="Target tenant whose evidence to export")
    scope_start: datetime = Field(..., description="Inclusive start of M&A window (tz-aware)")
    scope_end: datetime = Field(..., description="Inclusive end of M&A window (tz-aware)")


@router.post(
    "/ma-diligence",
    status_code=status.HTTP_200_OK,
    response_model=MaDiligenceExport,
    summary=(
        "Compose an M&A due diligence bundle covering every anchored day in the "
        "scope window for the target tenant"
    ),
    responses={
        200: {"description": "Sealed M&A bundle with manifest + packs + anchors + ma_root_hash"},
        401: {"description": "Authorization header missing or token invalid/expired"},
        403: {"description": "Principal's tenant_id does not match request tenant_id"},
        413: {
            "description": (
                "Scope window covers too many anchored days (max 366) or too many "
                "Receipts (max 100K) for synchronous export; narrow the window"
            )
        },
        422: {"description": "Invalid scope window (naive timestamps or inverted)"},
    },
)
async def export_ma_diligence(
    body: MaExportRequest,
    principal: Principal = Depends(get_principal),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> MaDiligenceExport:
    """Compose the M&A bundle and return it as JSON.

    Today: synchronous, returns the full bundle in one response. For very
    large scope windows (> 366 anchored days OR > 100K Receipts) the route
    returns 413 and the caller is expected to narrow the window or wait for
    the async-job variant (NEW-P12.X.ma-export-async-job).
    """
    if body.tenant_id != principal.tenant_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "tenant_mismatch",
                "reason": "tenant_id does not match authenticated principal.tenant_id",
            },
        )
    if body.scope_start.tzinfo is None or body.scope_end.tzinfo is None:
        raise HTTPException(
            status_code=422, detail="scope_start and scope_end must be timezone-aware"
        )
    if body.scope_end < body.scope_start:
        raise HTTPException(status_code=422, detail="scope_end must be >= scope_start")

    # 1. List every anchor row in scope, oldest-first.
    anchors_stmt = (
        select(TimestampAnchorRow)
        .where(
            TimestampAnchorRow.tenant_id == body.tenant_id,
            TimestampAnchorRow.anchor_date >= body.scope_start,
            TimestampAnchorRow.anchor_date <= body.scope_end,
        )
        .order_by(TimestampAnchorRow.anchor_date.asc())
        .limit(_MAX_PACKS_PER_BUNDLE + 1)
    )
    anchor_result = await session.execute(anchors_stmt)
    anchor_rows = list(anchor_result.scalars().all())
    if len(anchor_rows) > _MAX_PACKS_PER_BUNDLE:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Scope window covers more than {_MAX_PACKS_PER_BUNDLE} anchored "
                "days; narrow the window or request async export"
            ),
        )

    anchor_proofs: list[AnchorEvidence] = []
    evidence_packs: list[EvidencePack] = []
    now = datetime.now(UTC)

    # 2. For each anchored day, build one EvidencePack covering that day.
    for row in anchor_rows:
        anchor_evidence = AnchorEvidence.from_anchor_row(row)
        anchor_proofs.append(anchor_evidence)

        day_start = row.anchor_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        # Clip to the requested scope.
        chunk_start = max(day_start, body.scope_start)
        chunk_end = min(day_end, body.scope_end)

        pairs = await list_receipts_with_snapshot_for_tenant(
            session,
            body.tenant_id,
            scope_start=chunk_start,
            scope_end=chunk_end,
            limit=_MAX_RECEIPTS_PER_PACK + 1,
        )
        if len(pairs) > _MAX_RECEIPTS_PER_PACK:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"Day {row.anchor_date.date().isoformat()} contains more than "
                    f"{_MAX_RECEIPTS_PER_PACK} receipts; narrow the window"
                ),
            )

        pack = build_evidence_pack(
            tenant_id=body.tenant_id,
            generated_at=now,
            scope_start=chunk_start,
            scope_end=chunk_end,
            receipts_with_snapshots=pairs,
            anchor=anchor_evidence,
        )
        evidence_packs.append(pack)

    # 3. Compose and return the sealed bundle.
    try:
        return build_ma_diligence_export(
            tenant_id=body.tenant_id,
            scope_start=body.scope_start,
            scope_end=body.scope_end,
            generated_at=now,
            evidence_packs=evidence_packs,
            anchor_proofs=anchor_proofs,
        )
    except MaExportError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc

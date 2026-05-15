"""GET /v1/anchors - paginated list of TSA anchor rows for a tenant (CP9.22).

Exposes the TimestampAnchorRow surface from CP9.19 to investigators and
regulators. The anchor list answers "for which days does Forensa hold an
RFC 3161 TSA timestamp on this tenant's chain?" so a regulator can pick
a date and ask for proof.

Auth: same get_principal pattern as receipts/evidence routes. The
``tenant_id`` query parameter must match the authenticated principal's
tenant_id or the response is 403.
"""

from __future__ import annotations

import base64
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import Principal, get_principal
from apps.api.routes.receipts import get_session
from packages.ledger.models import TimestampAnchorRow

router = APIRouter(prefix="/v1", tags=["anchors"])

_MAX_LIMIT = 200


class AnchorListItem(BaseModel):
    """One TimestampAnchorRow in the list response.

    tsr_bytes and tsa_signature are base64-encoded for JSON transport.
    Both are None when status='deferred'.
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID
    tenant_id: UUID
    anchor_date: datetime
    status: str = Field(..., description="'anchored' or 'deferred'")
    root_hash: str | None
    tsa_identifier: str
    tsr_bytes_b64: str | None = Field(
        ..., description="RFC 3161 TimeStampResp DER bytes, base64-encoded; None if deferred"
    )
    tsa_signature_b64: str | None = Field(
        ..., description="TSA signature bytes, base64-encoded; None if deferred"
    )
    timestamped_at: datetime | None
    anchored_at: datetime


class AnchorListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: UUID
    items: list[AnchorListItem]
    count: int


def _to_item(row: TimestampAnchorRow) -> AnchorListItem:
    return AnchorListItem(
        id=row.id,
        tenant_id=row.tenant_id,
        anchor_date=row.anchor_date,
        status=row.status,
        root_hash=row.root_hash,
        tsa_identifier=row.tsa_identifier,
        tsr_bytes_b64=base64.b64encode(row.tsr_bytes).decode("ascii") if row.tsr_bytes else None,
        tsa_signature_b64=(
            base64.b64encode(row.tsa_signature).decode("ascii") if row.tsa_signature else None
        ),
        timestamped_at=row.timestamped_at,
        anchored_at=row.anchored_at,
    )


@router.get(
    "/anchors",
    status_code=status.HTTP_200_OK,
    response_model=AnchorListResponse,
    summary="List TSA timestamp anchors for a tenant (optionally bounded by date window)",
    responses={
        401: {"description": "Authorization header missing or token invalid/expired"},
        403: {"description": "Principal's tenant_id does not match query tenant_id"},
        422: {"description": "Invalid window or pagination params"},
    },
)
async def list_anchors(
    tenant_id: UUID = Query(..., description="Tenant whose anchors to list"),  # noqa: B008
    since: datetime | None = Query(  # noqa: B008
        default=None, description="Optional inclusive lower bound on anchor_date (tz-aware)"
    ),
    until: datetime | None = Query(  # noqa: B008
        default=None, description="Optional inclusive upper bound on anchor_date (tz-aware)"
    ),
    limit: int = Query(default=50, ge=1, le=_MAX_LIMIT),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(get_principal),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> AnchorListResponse:
    """Return a list of TimestampAnchorRow rows for ``tenant_id``.

    Rows are ordered by ``anchor_date DESC`` (most recent first).
    ``since`` and ``until`` are optional inclusive bounds on ``anchor_date``;
    if both are provided, ``until`` must be >= ``since``.
    """
    if tenant_id != principal.tenant_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "tenant_mismatch",
                "reason": "tenant_id query does not match authenticated principal.tenant_id",
            },
        )
    if since is not None and since.tzinfo is None:
        raise HTTPException(status_code=422, detail="since must be timezone-aware")
    if until is not None and until.tzinfo is None:
        raise HTTPException(status_code=422, detail="until must be timezone-aware")
    if since is not None and until is not None and until < since:
        raise HTTPException(status_code=422, detail="until must be >= since")

    stmt = select(TimestampAnchorRow).where(TimestampAnchorRow.tenant_id == tenant_id)
    if since is not None:
        stmt = stmt.where(TimestampAnchorRow.anchor_date >= since)
    if until is not None:
        stmt = stmt.where(TimestampAnchorRow.anchor_date <= until)
    stmt = stmt.order_by(TimestampAnchorRow.anchor_date.desc()).limit(limit).offset(offset)

    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    items = [_to_item(r) for r in rows]
    return AnchorListResponse(tenant_id=tenant_id, items=items, count=len(items))

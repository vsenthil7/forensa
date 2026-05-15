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

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import Principal, get_principal
from apps.api.routes.receipts import get_session
from packages.ledger.models import TimestampAnchorRow

router = APIRouter(prefix="/v1", tags=["anchors"])

_MAX_LIMIT = 200
_TSR_MEDIA_TYPE = "application/timestamp-reply"


def _wants_raw_tsr(accept: str | None) -> bool:
    """True iff the Accept header asks for the raw RFC 3161 TSR DER bytes.

    Conservative match: the header must literally contain the substring
    ``application/timestamp-reply``. Wildcards (``*/*``,
    ``application/*``) intentionally do NOT trigger the raw-DER path
    because the JSON form is the default machine-readable shape and the
    raw-DER path is meant for direct piping into ``openssl ts -verify``.
    """
    if not accept:
        return False
    return _TSR_MEDIA_TYPE in accept.lower()


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


@router.get(
    "/anchors/{anchor_id}",
    status_code=status.HTTP_200_OK,
    response_model=AnchorListItem,
    summary="Get a single TSA anchor with full TSR bytes for offline openssl ts -verify",
    responses={
        200: {
            "description": (
                "Anchor detail. JSON body by default; raw DER if "
                "Accept: application/timestamp-reply."
            ),
            "content": {
                "application/json": {},
                "application/timestamp-reply": {},
            },
        },
        401: {"description": "Authorization header missing or token invalid/expired"},
        403: {"description": "Anchor belongs to a different tenant"},
        404: {"description": "Anchor not found"},
        406: {
            "description": (
                "Raw-DER form requested but the anchor is deferred (no tsr_bytes available)"
            )
        },
    },
)
async def get_anchor_detail(
    anchor_id: UUID,
    principal: Principal = Depends(get_principal),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
    accept: str | None = Header(default=None),
) -> AnchorListItem | Response:
    """Return a single TimestampAnchorRow by id.

    Two wire forms via content negotiation:
      * ``Accept: application/json`` (default): full AnchorListItem JSON
        body with base64-encoded tsr_bytes_b64 + tsa_signature_b64 so an
        offline verifier can base64-decode and run ``openssl ts -verify``.
      * ``Accept: application/timestamp-reply``: raw RFC 3161 TSR DER
        bytes as binary body, suitable for direct piping into
        ``openssl ts -verify``. Only succeeds for anchored rows; deferred
        rows return 406 because there are no TSR bytes to ship.

    Authz: rows are tenant-scoped. A 404 hides the existence of anchors
    that belong to other tenants. A 403 fires when the row exists in the
    DB but belongs to a tenant other than the principal's - this case is
    distinguishable from 404 for honest API behaviour (the row exists,
    the caller just cannot see it).
    """
    stmt = select(TimestampAnchorRow).where(TimestampAnchorRow.id == anchor_id)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "anchor_not_found", "anchor_id": str(anchor_id)},
        )
    if row.tenant_id != principal.tenant_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "tenant_mismatch",
                "reason": "anchor belongs to a different tenant",
            },
        )

    if _wants_raw_tsr(accept):
        if row.tsr_bytes is None:
            raise HTTPException(
                status_code=406,
                detail={
                    "error": "no_tsr_bytes",
                    "reason": (
                        "raw RFC 3161 TSR bytes are only available for status='anchored' rows;"
                        " this row is deferred"
                    ),
                },
            )
        return Response(
            content=row.tsr_bytes,
            media_type=_TSR_MEDIA_TYPE,
            headers={
                "Content-Disposition": f'attachment; filename="anchor-{anchor_id}.tsr"',
                # X-Forensa-Anchor-Root-Hash lets a verifier cross-check the
                # raw TSR against the JSON form's root_hash without a 2nd call.
                "X-Forensa-Anchor-Root-Hash": row.root_hash or "",
            },
        )

    return _to_item(row)

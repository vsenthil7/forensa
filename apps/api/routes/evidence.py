"""GET /v1/evidence-packs - assemble evidence pack for a tenant over a window (CP6.4).

Lists every Receipt in [scope_start, scope_end] for the tenant via the existing
repositories.list_receipts_for_tenant + get_receipt_by_id repo functions, then
composes an EvidencePack with PROV-O lineage via packages.export.builder.

Returns the JSON-LD wire form including @context, @type, root_hash, receipts,
and activities arrays. Regulators can verify independently with the
packages.export.builder.verify_evidence_pack function (or any SHA-256 + JCS
canonical JSON implementation against the documented bind shape).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.routes.receipts import get_session
from packages.export.builder import build_evidence_pack
from packages.export.schema import EvidencePack
from packages.ledger.repositories import get_receipt_by_id, list_receipts_for_tenant

router = APIRouter(prefix="/v1", tags=["evidence"])

_MAX_RECEIPTS_PER_PACK = 1000


@router.get(
    "/evidence-packs",
    status_code=status.HTTP_200_OK,
    response_model=EvidencePack,
    summary="Assemble an evidence pack (JSON-LD + PROV-O) for a tenant",
    responses={
        413: {"description": "Window contains more than 1000 receipts"},
        422: {"description": "Invalid scope window"},
    },
)
async def export_evidence_pack(
    tenant_id: UUID = Query(..., description="Tenant whose evidence to export"),  # noqa: B008
    scope_start: datetime = Query(  # noqa: B008
        ..., description="Inclusive start of receipt window (RFC3339 timezone-aware)"
    ),
    scope_end: datetime = Query(  # noqa: B008
        ..., description="Inclusive end of receipt window (RFC3339 timezone-aware)"
    ),
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> EvidencePack:
    """Return a signed evidence pack for ``tenant_id`` covering [scope_start, scope_end]."""
    if scope_start.tzinfo is None or scope_end.tzinfo is None:
        raise HTTPException(
            status_code=422, detail="scope_start and scope_end must be timezone-aware"
        )
    if scope_end < scope_start:
        raise HTTPException(status_code=422, detail="scope_end must be >= scope_start")

    receipts = await list_receipts_for_tenant(
        session, tenant_id, limit=_MAX_RECEIPTS_PER_PACK + 1, offset=0
    )
    if len(receipts) > _MAX_RECEIPTS_PER_PACK:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Window contains more than {_MAX_RECEIPTS_PER_PACK} receipts;" " narrow the window"
            ),
        )

    # In-window filter and snapshot_id lookup
    pairs: list[tuple] = []
    for r in receipts:
        if scope_start <= r.signed_at <= scope_end:
            found = await get_receipt_by_id(session, r.id)
            # found is always not None here: receipt came from list_receipts_for_tenant
            # for the same tenant, so the same row exists for get_receipt_by_id.
            assert found is not None  # pragma: no cover  # nosec B101
            pairs.append(found)

    return build_evidence_pack(
        tenant_id=tenant_id,
        generated_at=datetime.now(UTC),
        scope_start=scope_start,
        scope_end=scope_end,
        receipts_with_snapshots=pairs,
    )

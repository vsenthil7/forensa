"""GET /v1/receipts - paginated list of receipts for a tenant.

Sorted by sequence DESC (most recently issued first). Backed by the
uq_receipts_tenant_sequence UNIQUE index (alembic 0001) for cheap pagination.
"""

from __future__ import annotations

import base64
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import Principal, get_principal
from packages.ledger.receipt_builder import recompute_receipt_hash
from packages.ledger.repositories import (
    get_receipt_by_id,
    list_receipts_for_tenant,
    list_receipts_for_tenant_cursor,
)
from packages.schema.receipt import Receipt

router = APIRouter(prefix="/v1", tags=["receipts"])


class ReceiptListItem(BaseModel):
    """One Receipt row in the list response. Signature is base64-encoded."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    tenant_id: UUID
    event_id: UUID
    policy_bundle_id: UUID
    sequence: int
    prev_receipt_hash: str | None
    payload_hash: str
    receipt_hash: str
    signature_b64: str = Field(..., description="Ed25519 signature, base64-encoded")
    signed_at: datetime

    @classmethod
    def from_receipt(cls, r: Receipt) -> ReceiptListItem:
        return cls(
            id=r.id,
            tenant_id=r.tenant_id,
            event_id=r.event_id,
            policy_bundle_id=r.policy_bundle_id,
            sequence=r.sequence,
            prev_receipt_hash=r.prev_receipt_hash,
            payload_hash=r.payload_hash,
            receipt_hash=r.receipt_hash,
            signature_b64=base64.b64encode(r.signature).decode("ascii"),
            signed_at=r.signed_at,
        )


class ReceiptListResponse(BaseModel):
    """Wrapped list response with pagination metadata.

    Two pagination modes - callers pick one per call, never both:

    - Cursor (preferred, O(log N) per page): pass ``before_sequence``.
      The response includes ``next_before_sequence`` = the smallest sequence
      in this page (or ``None`` if end of stream). Pass that back to the
      next call to get the next page.
    - Offset (legacy, slow past ~10K rows): pass ``offset``.
      ``next_before_sequence`` is still populated so callers can switch
      to cursor mode mid-stream without losing position.

    Optional ``signed_after`` / ``signed_before`` time-window filter
    (CP9.12 / NEW-P9.8.4) combines freely with either pagination mode.
    """

    model_config = ConfigDict(extra="forbid")

    items: list[ReceiptListItem]
    tenant_id: UUID
    limit: int
    offset: int = Field(
        ...,
        description="Echo of the offset used to fetch this page (0 if cursor mode)",
    )
    before_sequence: int | None = Field(
        None,
        description="Echo of the before_sequence cursor used to fetch this page",
    )
    next_before_sequence: int | None = Field(
        None,
        description=(
            "Cursor for the next page - pass as ``before_sequence`` to get"
            " older receipts. None if this is the last page."
        ),
    )
    signed_after: datetime | None = Field(
        None,
        description="Echo of the signed_after time-window filter used (CP9.12)",
    )
    signed_before: datetime | None = Field(
        None,
        description="Echo of the signed_before time-window filter used (CP9.12)",
    )
    count: int = Field(..., description="Number of items in this page (le limit)")


class ReceiptDetailResponse(BaseModel):
    """Full receipt detail with integrity-verification fields."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    tenant_id: UUID
    event_id: UUID
    policy_bundle_id: UUID
    policy_snapshot_id: UUID
    sequence: int
    prev_receipt_hash: str | None
    payload_hash: str
    receipt_hash: str
    signature_b64: str = Field(..., description="Ed25519 signature, base64-encoded")
    signed_at: datetime
    recomputed_receipt_hash: str = Field(
        ...,
        description="recompute_receipt_hash(receipt, snap_id); equals receipt_hash iff untampered",
    )
    integrity_ok: bool = Field(
        ...,
        description="True iff recomputed_receipt_hash matches stored receipt_hash",
    )


# Dependency factory - real wiring happens in app factory.
# Tests override this via app.dependency_overrides.
async def get_session() -> AsyncSession:  # pragma: no cover
    raise NotImplementedError("override via app.dependency_overrides at wire-up time")


@router.get(
    "/receipts",
    status_code=status.HTTP_200_OK,
    response_model=ReceiptListResponse,
    summary="List receipts for a tenant, newest first by sequence DESC",
)
async def list_receipts(
    tenant_id: UUID = Query(..., description="Tenant UUID whose receipts to list"),  # noqa: B008
    limit: int = Query(50, ge=1, le=200, description="Page size (1-200)"),
    offset: int = Query(
        0,
        ge=0,
        description=(
            "Zero-based offset for pagination (LEGACY - slow past ~10K rows)."
            " Prefer ``before_sequence`` cursor for production use."
        ),
    ),
    before_sequence: int | None = Query(
        None,
        ge=1,
        description=(
            "Cursor: return receipts with sequence < before_sequence."
            " Use the ``next_before_sequence`` from a prior response."
            " When set, ``offset`` is ignored."
        ),
    ),
    signed_after: datetime | None = Query(  # noqa: B008
        None,
        description=(
            "Time-window filter (CP9.12 / NEW-P9.8.4): only return Receipts"
            " with ``signed_at >= signed_after``. ISO-8601, must be"
            " timezone-aware. Inclusive lower bound."
        ),
    ),
    signed_before: datetime | None = Query(  # noqa: B008
        None,
        description=(
            "Time-window filter (CP9.12 / NEW-P9.8.4): only return Receipts"
            " with ``signed_at <= signed_before``. ISO-8601, must be"
            " timezone-aware. Inclusive upper bound."
        ),
    ),
    principal: Principal = Depends(get_principal),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> ReceiptListResponse:
    """Return up to ``limit`` Receipts for ``tenant_id``, sorted by sequence DESC.

    CP9.18c: refuses if ``tenant_id`` query param does not match the
    authenticated principal's tenant_id (403). Cross-tenant reads are
    blocked even when the token verifies.

    Cursor mode (preferred): pass ``before_sequence``. Offset mode (legacy):
    pass ``offset``. If both are passed, cursor wins and ``offset`` is
    echoed back as 0.

    Optional ``signed_after`` / ``signed_before`` time-window filter
    (CP9.12 / NEW-P9.8.4) combines freely with either pagination mode.
    Returns 422 if either time is naive (no tzinfo) or if
    ``signed_after > signed_before``.
    """
    # CP9.18c: cross-tenant read protection.
    if tenant_id != principal.tenant_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "tenant_mismatch",
                "reason": "tenant_id query does not match authenticated principal.tenant_id",
            },
        )
    # Validation: timezone-awareness + ordering.
    if signed_after is not None and signed_after.tzinfo is None:
        raise HTTPException(
            status_code=422,
            detail="signed_after must be timezone-aware (ISO-8601 with offset)",
        )
    if signed_before is not None and signed_before.tzinfo is None:
        raise HTTPException(
            status_code=422,
            detail="signed_before must be timezone-aware (ISO-8601 with offset)",
        )
    if signed_after is not None and signed_before is not None and signed_after > signed_before:
        raise HTTPException(
            status_code=422,
            detail="signed_after must be <= signed_before",
        )

    if before_sequence is not None:
        receipts = await list_receipts_for_tenant_cursor(
            session,
            tenant_id,
            limit=limit,
            before_sequence=before_sequence,
            signed_after=signed_after,
            signed_before=signed_before,
        )
        echoed_offset = 0
    else:
        receipts = await list_receipts_for_tenant(
            session,
            tenant_id,
            limit=limit,
            offset=offset,
            signed_after=signed_after,
            signed_before=signed_before,
        )
        echoed_offset = offset

    items = [ReceiptListItem.from_receipt(r) for r in receipts]
    # Cursor for the next page: smallest sequence in this page, or None if
    # the page is empty (end of stream) or shorter than the limit (also end).
    next_cursor: int | None = None if len(receipts) < limit else min(r.sequence for r in receipts)
    return ReceiptListResponse(
        items=items,
        tenant_id=tenant_id,
        limit=limit,
        offset=echoed_offset,
        before_sequence=before_sequence,
        next_before_sequence=next_cursor,
        signed_after=signed_after,
        signed_before=signed_before,
        count=len(items),
    )


@router.get(
    "/receipts/{receipt_id}",
    status_code=status.HTTP_200_OK,
    response_model=ReceiptDetailResponse,
    summary="Fetch one Receipt by id and verify chain integrity",
    responses={404: {"description": "Receipt not found"}},
)
async def get_receipt(
    receipt_id: UUID,
    principal: Principal = Depends(get_principal),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> ReceiptDetailResponse:
    """Return full Receipt detail plus a live integrity check.

    CP9.18c: refuses if the persisted receipt's tenant_id does not match
    the authenticated principal's tenant_id (403). A leaked receipt UUID
    is still not enough to read another tenant's data.

    The recomputed_receipt_hash is computed from the stored fields and the
    snapshot id; if it does not equal the stored receipt_hash, integrity_ok
    is False and the row should be treated as tampered.
    """
    found = await get_receipt_by_id(session, receipt_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Receipt not found")
    receipt, snapshot_id = found
    # CP9.18c: refuse cross-tenant detail read AFTER the row is loaded so
    # the 403 message doesn't act as an oracle ("this id exists for some
    # tenant"). The same 404 surface would also be acceptable; we choose
    # 403 because it's the truthful answer for an authenticated principal.
    if receipt.tenant_id != principal.tenant_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "tenant_mismatch",
                "reason": "receipt belongs to a different tenant than the principal",
            },
        )
    recomputed = recompute_receipt_hash(receipt, snapshot_id)
    return ReceiptDetailResponse(
        id=receipt.id,
        tenant_id=receipt.tenant_id,
        event_id=receipt.event_id,
        policy_bundle_id=receipt.policy_bundle_id,
        policy_snapshot_id=snapshot_id,
        sequence=receipt.sequence,
        prev_receipt_hash=receipt.prev_receipt_hash,
        payload_hash=receipt.payload_hash,
        receipt_hash=receipt.receipt_hash,
        signature_b64=base64.b64encode(receipt.signature).decode("ascii"),
        signed_at=receipt.signed_at,
        recomputed_receipt_hash=recomputed,
        integrity_ok=(recomputed == receipt.receipt_hash),
    )

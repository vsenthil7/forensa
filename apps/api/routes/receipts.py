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

from packages.ledger.receipt_builder import recompute_receipt_hash
from packages.ledger.repositories import get_receipt_by_id, list_receipts_for_tenant
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
    """Wrapped list response with pagination metadata."""

    model_config = ConfigDict(extra="forbid")

    items: list[ReceiptListItem]
    tenant_id: UUID
    limit: int
    offset: int
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
    offset: int = Query(0, ge=0, description="Zero-based offset for pagination"),
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> ReceiptListResponse:
    """Return up to limit Receipts for tenant_id, sorted by sequence DESC."""
    receipts = await list_receipts_for_tenant(session, tenant_id, limit=limit, offset=offset)
    items = [ReceiptListItem.from_receipt(r) for r in receipts]
    return ReceiptListResponse(
        items=items,
        tenant_id=tenant_id,
        limit=limit,
        offset=offset,
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
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> ReceiptDetailResponse:
    """Return full Receipt detail plus a live integrity check.

    The recomputed_receipt_hash is computed from the stored fields and the
    snapshot id; if it does not equal the stored receipt_hash, integrity_ok
    is False and the row should be treated as tampered.
    """
    found = await get_receipt_by_id(session, receipt_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Receipt not found")
    receipt, snapshot_id = found
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

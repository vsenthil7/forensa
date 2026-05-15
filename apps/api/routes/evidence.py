"""GET /v1/evidence-packs - assemble evidence pack for a tenant over a window (CP6.4).

Lists every Receipt in [scope_start, scope_end] for the tenant via the existing
repositories.list_receipts_for_tenant + get_receipt_by_id repo functions, then
composes an EvidencePack with PROV-O lineage via packages.export.builder.

Returns the JSON-LD wire form including @context, @type, root_hash, receipts,
and activities arrays by default. With ``Accept: application/pdf`` (CP9.21b),
the same pack is rendered to a regulator-grade PDF via
packages.export.pdf_renderer and streamed back with the appropriate
Content-Disposition: attachment header so a browser triggers a download.

Regulators can verify independently with the
packages.export.builder.verify_evidence_pack function (or any SHA-256 + JCS
canonical JSON implementation against the documented bind shape). The PDF is
a deterministic rendering of the same pack content bound by root_hash, so it
can be cross-checked against the JSON-LD form.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import Principal, get_principal
from apps.api.routes.receipts import get_session
from packages.export.builder import build_evidence_pack
from packages.export.pdf_renderer import render_evidence_pack_pdf
from packages.export.schema import EvidencePack
from packages.ledger.repositories import list_receipts_with_snapshot_for_tenant

router = APIRouter(prefix="/v1", tags=["evidence"])

_MAX_RECEIPTS_PER_PACK = 1000
_PDF_MEDIA_TYPE = "application/pdf"


def _wants_pdf(accept: str | None) -> bool:
    """True iff the Accept header asks for application/pdf.

    Conservative match: the header must literally contain the substring
    ``application/pdf``. Wildcards (``*/*``, ``application/*``) intentionally
    do NOT trigger PDF because the JSON-LD form is the default machine-
    readable shape and we want the PDF path opted into explicitly.
    """
    if not accept:
        return False
    return _PDF_MEDIA_TYPE in accept.lower()


@router.get(
    "/evidence-packs",
    status_code=status.HTTP_200_OK,
    response_model=EvidencePack,
    summary="Assemble an evidence pack (JSON-LD + PROV-O, or PDF) for a tenant",
    responses={
        200: {
            "description": "Evidence pack. JSON-LD by default; PDF if Accept: application/pdf.",
            "content": {
                "application/json": {},
                "application/pdf": {},
            },
        },
        401: {"description": "Authorization header missing or token invalid/expired"},
        403: {"description": "Principal's tenant_id does not match the query tenant_id"},
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
    principal: Principal = Depends(get_principal),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
    accept: str | None = Header(default=None),
) -> EvidencePack | Response:
    """Return an evidence pack for ``tenant_id`` covering [scope_start, scope_end].

    Two wire forms via content negotiation:
      * ``Accept: application/json`` (default): JSON-LD with @context, @type,
        root_hash, receipts, activities.
      * ``Accept: application/pdf``: deterministic A4 PDF rendering of the
        same pack content, with Content-Disposition: attachment so browsers
        trigger a download. Filename includes the first 12 chars of
        root_hash so two PDFs for different packs never collide.

    CP9.18c: refuses if ``tenant_id`` query does not match the authenticated
    principal's tenant_id (403). Cross-tenant evidence export is blocked
    irrespective of the requested wire form.
    """
    # CP9.18c: cross-tenant export protection.
    if tenant_id != principal.tenant_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "tenant_mismatch",
                "reason": "tenant_id query does not match authenticated principal.tenant_id",
            },
        )
    if scope_start.tzinfo is None or scope_end.tzinfo is None:
        raise HTTPException(
            status_code=422, detail="scope_start and scope_end must be timezone-aware"
        )
    if scope_end < scope_start:
        raise HTTPException(status_code=422, detail="scope_end must be >= scope_start")

    # CP9.7: single JOIN-ish query replaces the old list_receipts +
    # per-receipt get_receipt_by_id N+1 loop. Server-side signed_at filter is
    # applied via the (tenant_id, signed_at) composite index.
    pairs = await list_receipts_with_snapshot_for_tenant(
        session,
        tenant_id,
        scope_start=scope_start,
        scope_end=scope_end,
        limit=_MAX_RECEIPTS_PER_PACK + 1,
    )
    if len(pairs) > _MAX_RECEIPTS_PER_PACK:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Window contains more than {_MAX_RECEIPTS_PER_PACK} receipts;" " narrow the window"
            ),
        )

    pack = build_evidence_pack(
        tenant_id=tenant_id,
        generated_at=datetime.now(UTC),
        scope_start=scope_start,
        scope_end=scope_end,
        receipts_with_snapshots=pairs,
    )

    # CP9.21b: content negotiation. PDF when Accept asks for it, else JSON-LD.
    if _wants_pdf(accept):
        pdf_bytes = render_evidence_pack_pdf(pack)
        filename = f"evidence-pack-{pack.root_hash[:12]}.pdf"
        return Response(
            content=pdf_bytes,
            media_type=_PDF_MEDIA_TYPE,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                # X-Forensa-Root-Hash lets a verifier cross-check the PDF
                # against the JSON-LD form without re-rendering.
                "X-Forensa-Root-Hash": pack.root_hash,
            },
        )

    return pack

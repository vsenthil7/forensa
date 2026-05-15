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

CP9.36 / NEW-P10.X.ma-export-encryption-at-rest: optional encryption at
rest. When the caller provides ``?encrypt_for_pubkey_b64=<32B base64>``,
the route serialises the assembled MaDiligenceExport to canonical JSON,
encrypts those bytes with packages.crypto.encrypt.encrypt_for_recipient
under the supplied X25519 public key, and returns a CipherEnvelope
instead of the raw bundle. The acquirer holds the paired X25519 private
key and uses decrypt_for_recipient to recover the bundle JSON. When the
query param is omitted, behaviour is unchanged (raw bundle returned).

Authz: same as evidence-pack route. The body's ``tenant_id`` MUST match
the authenticated principal's tenant_id. Cross-tenant access is 403.

Why POST not GET: M&A scope windows can be very wide (12-24 months);
the natural shape is a JSON request body. Also leaves room for future
filters (specific agent ids, specific event kinds) without query-string
explosion.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import Principal, get_principal
from apps.api.routes.receipts import get_session
from packages.crypto.encrypt import (
    CipherEnvelope,
    EncryptError,
    encrypt_for_recipient,
)
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
    response_model=MaDiligenceExport | CipherEnvelope,
    summary=(
        "Compose an M&A due diligence bundle covering every anchored day in the "
        "scope window for the target tenant; optionally encrypt for an acquirer pubkey"
    ),
    responses={
        200: {
            "description": (
                "Sealed M&A bundle (raw MaDiligenceExport) OR a CipherEnvelope"
                " wrapping the serialised bundle when encrypt_for_pubkey_b64 is set"
            )
        },
        401: {"description": "Authorization header missing or token invalid/expired"},
        403: {"description": "Principal's tenant_id does not match request tenant_id"},
        413: {
            "description": (
                "Scope window covers too many anchored days (max 366) or too many "
                "Receipts (max 100K) for synchronous export; narrow the window"
            )
        },
        422: {
            "description": (
                "Invalid scope window (naive timestamps or inverted) OR malformed"
                " encrypt_for_pubkey_b64 (not base64 or wrong length)"
            )
        },
    },
)
async def export_ma_diligence(
    body: MaExportRequest,
    encrypt_for_pubkey_b64: str | None = Query(
        None,
        description=(
            "Optional URL-safe-base64-encoded 32-byte X25519 public key of the acquirer."
            " When provided, the response is a CipherEnvelope wrapping the serialised"
            " MaDiligenceExport JSON, encrypted with X25519+ChaCha20-Poly1305 so only"
            " the holder of the paired private key can decrypt. When omitted, the"
            " response is the raw MaDiligenceExport (CP9.28 behaviour). Use"
            " RFC 4648 section 5 url-safe base64 (alphabet a-zA-Z0-9-_); trailing"
            " `=` padding is optional."
        ),
    ),
    principal: Principal = Depends(get_principal),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> MaDiligenceExport | CipherEnvelope:
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

    # 3. Compose the sealed bundle.
    try:
        export = build_ma_diligence_export(
            tenant_id=body.tenant_id,
            scope_start=body.scope_start,
            scope_end=body.scope_end,
            generated_at=now,
            evidence_packs=evidence_packs,
            anchor_proofs=anchor_proofs,
        )
    except MaExportError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc

    # 4. Optional encryption at rest (CP9.36 / NEW-P10.X.ma-export-encryption-at-rest).
    #
    # When the caller supplies an acquirer X25519 public key, serialise
    # the export to canonical JSON bytes and wrap it in a CipherEnvelope.
    # The acquirer holds the paired private key and uses decrypt_for_recipient
    # to recover the bundle. The export's ma_root_hash + platform_signature
    # (when CP9.34-signed) remain valid after decrypt -- encryption is
    # purely a confidentiality-at-rest layer, NOT a replacement for integrity
    # or provenance proofs.
    #
    # Encoding: URL-safe base64 (RFC 4648 section 5). The standard b64
    # alphabet uses + and / which need URL-escaping; urlsafe uses - and _
    # which don't. JWK + certificate distribution all use urlsafe, so the
    # acquirer's existing key tooling produces the right shape. We accept
    # both with and without trailing `=` padding.
    if encrypt_for_pubkey_b64 is None:
        return export
    # Add padding if missing (urlsafe-b64 may strip it; b64 decoders care).
    padded = encrypt_for_pubkey_b64 + "=" * (-len(encrypt_for_pubkey_b64) % 4)
    try:
        recipient_public_key = base64.urlsafe_b64decode(padded)
    except (ValueError, base64.binascii.Error) as exc:  # type: ignore[attr-defined]
        raise HTTPException(
            status_code=422,
            detail=f"encrypt_for_pubkey_b64 is not valid base64: {exc}",
        ) from exc
    plaintext = export.model_dump_json().encode("utf-8")
    try:
        return encrypt_for_recipient(plaintext, recipient_public_key=recipient_public_key)
    except EncryptError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

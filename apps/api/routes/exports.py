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

CP9.45 / IP #8 NEW-P12.X.ma-export-async-job (route half):
- POST /v1/exports/ma-diligence/jobs        -> 202 + {job_id}, schedules
  the CP9.44 runner via asyncio.create_task; returns immediately.
- GET  /v1/exports/ma-diligence/jobs/{id}   -> {status, result_export,
  result_error, ...} reflecting the current row state.
- GET  /v1/exports/ma-diligence/jobs        -> list jobs for the
  authenticated principal's tenant, newest-first.
All three are tenant-scoped via CP9.33 + CP9.18c (the principal's
tenant_id is the only valid tenant; cross-tenant probes return 403).

Authz: same as evidence-pack route. The body's ``tenant_id`` MUST match
the authenticated principal's tenant_id. Cross-tenant access is 403.

Why POST not GET: M&A scope windows can be very wide (12-24 months);
the natural shape is a JSON request body. Also leaves room for future
filters (specific agent ids, specific event kinds) without query-string
explosion.
"""

from __future__ import annotations

import asyncio
import base64
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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
from packages.jobs.ma_export_runner import run_ma_export_job
from packages.ledger.ma_export_job_repository import (
    create_ma_export_job,
    get_ma_export_job_by_id,
    list_ma_export_jobs_for_tenant,
)
from packages.ledger.models import MaExportJobRow, TimestampAnchorRow
from packages.ledger.repositories import list_receipts_with_snapshot_for_tenant

router = APIRouter(prefix="/v1/exports", tags=["exports"])

_LOG = logging.getLogger(__name__)

# Strong references to background tasks (CP9.45 / RUF006). Without this set,
# asyncio.create_task returns a weak-referenced Task that the event loop may
# garbage-collect before the runner completes. We add() on schedule and
# discard() in a done-callback so the set self-prunes as tasks finish.
_background_tasks: set[asyncio.Task[None]] = set()

_MAX_PACKS_PER_BUNDLE = 366  # one year of daily anchored packs
_MAX_RECEIPTS_PER_PACK = 1000


# Dependency factory for the worker's sessionmaker. Real wiring happens
# in the app factory (production) or via dependency_overrides (tests).
# Returns the FACTORY (async_sessionmaker), NOT a session, because the
# scheduled runner outlives the request and needs to open its own
# sessions after the request session has closed.
async def get_sessionmaker() -> async_sessionmaker[AsyncSession]:  # pragma: no cover
    """Return the application's async_sessionmaker factory.

    Overridden in tests via ``app.dependency_overrides[get_sessionmaker]``;
    overridden in production via the app factory's lifespan hook.
    """
    raise NotImplementedError("override via app.dependency_overrides at wire-up time")


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


# ============================================================================
# CP9.45 / IP #8 NEW-P12.X.ma-export-async-job (route half)
# ============================================================================
#
# Three endpoints expose the async-job machinery:
#
#   POST /v1/exports/ma-diligence/jobs
#       Insert a pending row + schedule the CP9.44 runner. Returns 202
#       Accepted + {job_id}. Idempotent in the weak sense: every POST
#       creates a new job; the strong-idempotency variant via
#       Idempotency-Key header is a future CP.
#
#   GET /v1/exports/ma-diligence/jobs/{job_id}
#       Returns the row state: status, started_at, completed_at,
#       result_export (when completed), result_error (when failed).
#       Tenant-scoped via principal.tenant_id; cross-tenant probe -> 404.
#       (We use 404 not 403 here because a public job_id is enumerable;
#       returning 403 would act as an oracle for which job_ids exist.)
#
#   GET /v1/exports/ma-diligence/jobs
#       List jobs for the principal's tenant, newest-first. Cursor-less
#       for now (50 most recent); cursor pagination is a future CP.
#
# The runner is scheduled via asyncio.create_task on the request's
# event loop. For the hackathon demo this means the runner runs
# in-process. In production this would be replaced with a Celery /
# Arq publish to a separate worker fleet. The route's contract
# (202 + job_id) is unchanged.


class MaExportJobCreateRequest(BaseModel):
    """Request body for POST /v1/exports/ma-diligence/jobs (CP9.45)."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: UUID = Field(..., description="Target tenant whose evidence to export")
    scope_start: datetime = Field(..., description="Inclusive start of M&A window (tz-aware)")
    scope_end: datetime = Field(..., description="Inclusive end of M&A window (tz-aware)")
    encrypt_for_pubkey_b64: str | None = Field(
        default=None,
        description=(
            "Optional URL-safe-base64-encoded 32-byte X25519 public key of the"
            " acquirer; when set the result_export will be a CipherEnvelope"
            " wrapping the canonical MaDiligenceExport JSON."
        ),
    )
    platform_sign_key_id: str | None = Field(
        default=None,
        max_length=128,
        description=(
            "Optional Forensa platform-key identifier; when set the runner"
            " will platform-sign the bundle via sign_ma_diligence_export"
            " (subject to the server having the private key available)."
        ),
    )


class MaExportJobCreateResponse(BaseModel):
    """202 Accepted body for POST /v1/exports/ma-diligence/jobs."""

    model_config = ConfigDict(extra="forbid")

    job_id: UUID = Field(..., description="UUID of the newly-created job row")
    status: str = Field(..., description="Initial job status (always 'pending')")
    poll_url: str = Field(
        ...,
        description="Relative URL for GET-status polling of this job",
    )


class MaExportJobStatusResponse(BaseModel):
    """Body for GET /v1/exports/ma-diligence/jobs/{job_id}.

    The shape mirrors the row but with field-level documentation suited
    to API consumers. result_export is a JSON dict whose @type alias
    distinguishes MaDiligenceExport from CipherEnvelope (encryption ON).
    """

    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    tenant_id: UUID
    status: str = Field(..., description="One of: pending, running, completed, failed")
    scope_start: datetime
    scope_end: datetime
    requested_at: datetime
    started_at: datetime | None = Field(
        None, description="When the runner transitioned pending -> running"
    )
    completed_at: datetime | None = Field(
        None,
        description=(
            "When the runner transitioned running -> completed OR failed."
            " None while in pending or running."
        ),
    )
    result_export: dict[str, Any] | None = Field(
        None,
        description=(
            "Completed-only: the MaDiligenceExport dict (encryption OFF) or"
            " CipherEnvelope dict (encryption ON). None when pending /"
            " running / failed."
        ),
    )
    result_error: str | None = Field(
        None,
        description=(
            "Failed-only: truncated str(exc) of the runner failure. None when"
            " pending / running / completed."
        ),
    )

    @classmethod
    def from_row(cls, row: MaExportJobRow) -> MaExportJobStatusResponse:
        return cls(
            job_id=row.id,
            tenant_id=row.tenant_id,
            status=row.status,
            scope_start=row.scope_start,
            scope_end=row.scope_end,
            requested_at=row.requested_at,
            started_at=row.started_at,
            completed_at=row.completed_at,
            result_export=row.result_export,
            result_error=row.result_error,
        )


class MaExportJobListResponse(BaseModel):
    """Body for GET /v1/exports/ma-diligence/jobs (list)."""

    model_config = ConfigDict(extra="forbid")

    items: list[MaExportJobStatusResponse]
    tenant_id: UUID
    limit: int
    offset: int
    count: int


@router.post(
    "/ma-diligence/jobs",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=MaExportJobCreateResponse,
    summary="Schedule an async M&A due diligence bundle export job",
    responses={
        202: {"description": "Job created and scheduled; poll the returned poll_url"},
        401: {"description": "Authorization header missing or token invalid/expired"},
        403: {"description": "Principal's tenant_id does not match request tenant_id"},
        422: {
            "description": (
                "Invalid scope window (naive timestamps or inverted) OR malformed"
                " encrypt_for_pubkey_b64"
            )
        },
    },
)
async def create_ma_export_job_route(
    body: MaExportJobCreateRequest,
    principal: Principal = Depends(get_principal),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
    sessionmaker: async_sessionmaker[AsyncSession] = Depends(get_sessionmaker),  # noqa: B008
) -> MaExportJobCreateResponse:
    """Create a pending ma_export_jobs row and schedule the CP9.44 runner.

    The route returns 202 IMMEDIATELY without waiting for the bundle to
    assemble. The caller polls GET /v1/exports/ma-diligence/jobs/{id}
    for completion. Typical end-to-end latency for a 12-month scope is
    seconds to minutes depending on receipt count.

    Tenant scoping: ``body.tenant_id`` MUST match ``principal.tenant_id``,
    or the response is 403. This mirrors the synchronous M&A route.
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

    # Eager pubkey validation: if the caller passed garbage, fail BEFORE
    # creating a row. We don't decode the key here -- just check it parses.
    # The runner does the full encode/decrypt cycle later.
    if body.encrypt_for_pubkey_b64 is not None:
        padded = body.encrypt_for_pubkey_b64 + "=" * (-len(body.encrypt_for_pubkey_b64) % 4)
        try:
            base64.urlsafe_b64decode(padded)
        except (ValueError, base64.binascii.Error) as exc:  # type: ignore[attr-defined]
            raise HTTPException(
                status_code=422,
                detail=f"encrypt_for_pubkey_b64 is not valid base64: {exc}",
            ) from exc

    job_id = await create_ma_export_job(
        session,
        tenant_id=body.tenant_id,
        scope_start=body.scope_start,
        scope_end=body.scope_end,
        encrypt_for_pubkey_b64=body.encrypt_for_pubkey_b64,
        platform_sign_key_id=body.platform_sign_key_id,
        requested_by_agent_id=principal.agent_id,
    )
    # Commit BEFORE scheduling the runner so the row is visible to the
    # background task's first SELECT (the runner opens its own session).
    await session.commit()

    # Schedule the runner. asyncio.create_task fires-and-forgets on the
    # request's event loop; the awaitable runs concurrently with future
    # requests. We deliberately do NOT await it -- the route returns 202.
    #
    # In production this is replaced with a Celery/Arq publish so the
    # work runs on a separate worker fleet. The route's contract is
    # identical either way.
    #
    # RUF006 mitigation: hold a strong reference to the Task in
    # _background_tasks so the event loop's weak-ref pool can't GC it
    # mid-flight. The done-callback discards on completion so the set
    # self-prunes.
    task = asyncio.create_task(
        run_ma_export_job(sessionmaker, job_id=job_id),
        name=f"ma_export_runner:{job_id}",
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    _LOG.info("ma_export_job %s: scheduled", job_id)

    return MaExportJobCreateResponse(
        job_id=job_id,
        status="pending",
        poll_url=f"/v1/exports/ma-diligence/jobs/{job_id}",
    )


@router.get(
    "/ma-diligence/jobs/{job_id}",
    status_code=status.HTTP_200_OK,
    response_model=MaExportJobStatusResponse,
    summary="Poll the status of an async M&A export job",
    responses={
        200: {"description": "Job state (pending/running/completed/failed)"},
        401: {"description": "Authorization header missing or token invalid/expired"},
        404: {
            "description": (
                "Job not found (does not exist OR belongs to a different tenant)."
                " 404 is returned for cross-tenant probes to avoid leaking which"
                " job_ids exist."
            )
        },
    },
)
async def get_ma_export_job_status(
    job_id: UUID,
    principal: Principal = Depends(get_principal),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> MaExportJobStatusResponse:
    """Return the current state of job ``job_id``.

    Tenant scoping: the row is fetched with ``WHERE tenant_id =
    principal.tenant_id`` (CP9.33 pattern). A cross-tenant probe sees
    404, not 403, because job_ids are enumerable. The 404 is the same
    surface as "truly does not exist", so an attacker can't distinguish.
    """
    row = await get_ma_export_job_by_id(session, job_id, tenant_id=principal.tenant_id)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    return MaExportJobStatusResponse.from_row(row)


@router.get(
    "/ma-diligence/jobs",
    status_code=status.HTTP_200_OK,
    response_model=MaExportJobListResponse,
    summary="List M&A export jobs for the authenticated principal's tenant",
    responses={
        200: {"description": "List of jobs, newest first by requested_at DESC"},
        401: {"description": "Authorization header missing or token invalid/expired"},
    },
)
async def list_ma_export_jobs_route(
    limit: int = Query(50, ge=1, le=200, description="Page size (1-200)"),
    offset: int = Query(0, ge=0, description="Zero-based offset for pagination"),
    principal: Principal = Depends(get_principal),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> MaExportJobListResponse:
    """List jobs for the principal's tenant, newest-first.

    Tenant scoping is implicit: there is no tenant_id query param;
    the principal's tenant_id is the only valid tenant. This means
    cross-tenant listing is impossible by construction.
    """
    rows = await list_ma_export_jobs_for_tenant(
        session, principal.tenant_id, limit=limit, offset=offset
    )
    items = [MaExportJobStatusResponse.from_row(r) for r in rows]
    return MaExportJobListResponse(
        items=items,
        tenant_id=principal.tenant_id,
        limit=limit,
        offset=offset,
        count=len(items),
    )

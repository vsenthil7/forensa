"""CP9.44 / IP #8 NEW-P12.X.ma-export-async-job (runner half).

Pure execution layer for M&A export jobs. Takes a persisted job_id,
drives it through the state machine, composes the export pipeline,
and writes the result back to the row. NO route changes here -- the
route that schedules this runner ships as CP9.45.

The runner is independent of the HTTP route by design. In production it
will be invoked by a separate worker process (Celery / Arq /
EventBridge consumer). For the hackathon demo CP9.45 schedules it
via asyncio.create_task on the request handler's event loop, but the
runner doesn't know or care which scheduler called it.

Session lifecycle
-----------------

The runner owns its OWN sessions. It does NOT borrow the HTTP route's
session because the route returns 202 immediately and its session is
closed by the time the runner runs. Two distinct sessions per job:

  Session A: mark pending -> running, commit immediately so a GET-status
    call sees the transition right away. This is the "lock" stage.
  Session B: fetch the job row, read the export params, do the full
    export pipeline (anchor list + per-day receipt lists + build pack
    + build ma export + optional sign + optional encrypt), then mark
    running -> completed with the result payload. Single commit at the
    end so the result + status transition are atomic.

On ANY exception during Session B, we open Session C to mark the row
running -> failed with the truncated error message. Session C is a
clean session because Session B may be in an aborted-transaction state.

Pipeline composition
--------------------

Mirrors apps/api/routes/exports.py:export_ma_diligence (CP9.28 / 9.34 /
9.36) but factored as a worker:

  1. List anchors in scope -> AnchorEvidence list
  2. For each anchor, list (receipt, snapshot) pairs for that day
  3. Build one EvidencePack per anchor
  4. Build the MaDiligenceExport
  5. Optional: sign with platform private key (CP9.34)
  6. Optional: encrypt for acquirer pubkey (CP9.36) via the CP9.41
     X25519PrivateKeyProvider abstraction -- but the runner does ENCRYPT
     not decrypt, so it uses encrypt_for_recipient directly with the
     pubkey bytes from the job row.

Job-row size budgets
--------------------

The runner reuses the existing in-route caps:
  _MAX_PACKS_PER_BUNDLE   366  (one year of anchored days)
  _MAX_RECEIPTS_PER_PACK 1000
If either cap is exceeded mid-job, the runner marks the job failed
with the same error message the synchronous route would have surfaced.

Error truncation
----------------

The repository layer truncates result_error at 2048 chars (CP9.43). The
runner therefore doesn't need to truncate; it can pass the full
str(exc) and trust the repo to bound the row size.

Test surface
------------

The runner is pure-async, takes a sessionmaker factory + job_id +
optional signing key + optional encryption pubkey. Tests mock the
sessionmaker to script the SQL responses + assert state-machine
transitions. PG-integration tests exercise the runner end-to-end
against a seeded ma_export_jobs row.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.crypto.encrypt import (
    EncryptError,
    encrypt_for_recipient,
)
from packages.export.builder import build_evidence_pack
from packages.export.ma_export import (
    MaDiligenceExport,
    MaExportError,
    MaExportSignatureError,
    build_ma_diligence_export,
    sign_ma_diligence_export,
)
from packages.export.schema import AnchorEvidence, EvidencePack
from packages.ledger.ma_export_job_repository import (
    MaExportJobStateError,
    get_ma_export_job_by_id,
    mark_ma_export_job_failed,
    mark_ma_export_job_pending_to_running,
    mark_ma_export_job_running_to_completed,
)
from packages.ledger.models import TimestampAnchorRow
from packages.ledger.repositories import list_receipts_with_snapshot_for_tenant

__all__ = [
    "MaExportRunnerError",
    "run_ma_export_job",
]

_LOG = logging.getLogger(__name__)

_MAX_PACKS_PER_BUNDLE = 366
_MAX_RECEIPTS_PER_PACK = 1000


class MaExportRunnerError(RuntimeError):
    """Raised by run_ma_export_job for runner-internal failures.

    Distinct from MaExportError (validation failures in build) and
    MaExportSignatureError (signing failures): MaExportRunnerError
    covers "the runner couldn't even start" cases like a missing job
    row. End-state-machine errors are funnelled into result_error via
    mark_ma_export_job_failed.
    """


async def run_ma_export_job(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    job_id: UUID,
    platform_signing_key: bytes | None = None,
) -> None:
    """Drive job ``job_id`` from pending -> running -> completed (or failed).

    Two-session lifecycle:

      Session A: lock the job (pending -> running) + commit immediately.
        Any GET-status call after this point sees the transition.

      Session B: do the work. Fetch the job's params, run the export
        pipeline, optionally sign + encrypt, mark running -> completed
        with the result payload + commit. One commit at the end so
        the status + result are atomic.

      Session C (on exception during B): mark running -> failed with
        the str(exc) message + commit. Session B may be in an aborted
        transaction state so a fresh session is needed.

    Parameters
    ----------
    sessionmaker : async_sessionmaker
        Factory for AsyncSession instances. The runner opens its own
        sessions; do NOT pass an open session.
    job_id : UUID
        The ma_export_jobs row to drive. Must exist and be in
        status='pending'.
    platform_signing_key : bytes | None
        Optional 32-byte Ed25519 private key. When provided AND the
        job row's ``platform_sign_key_id`` is non-None, the assembled
        MaDiligenceExport is platform-signed before being persisted as
        the result. When omitted (or the job row has no key_id), the
        bundle is unsigned (backwards-compat with CP9.28 bundles).
        In production this comes from KMS; today it's a bytes-in stub.

    Raises
    ------
    MaExportRunnerError
        Only if the job row doesn't exist or is not in 'pending' status
        at the time the runner is invoked. End-of-pipeline failures
        (build, sign, encrypt) are caught and recorded as the job's
        result_error rather than re-raised.
    """
    # ---- Session A: lock the job ----
    async with sessionmaker() as session_a:
        try:
            await mark_ma_export_job_pending_to_running(session_a, job_id)
            await session_a.commit()
        except MaExportJobStateError as exc:
            await session_a.rollback()
            raise MaExportRunnerError(f"cannot start ma export job {job_id}: {exc}") from exc

    _LOG.info("ma_export_job %s: running", job_id)

    # ---- Session B: do the work ----
    try:
        async with sessionmaker() as session_b:
            row = await get_ma_export_job_by_id(session_b, job_id)
            if row is None:
                # Race: the row was deleted between Session A and B. Treat
                # as a runner failure (not a job-state failure since there
                # is no row to write the failure to).
                raise MaExportRunnerError(
                    f"ma export job {job_id} disappeared between lock + work stages"
                )
            tenant_id = row.tenant_id
            scope_start = row.scope_start
            scope_end = row.scope_end
            encrypt_pubkey_b64 = row.encrypt_for_pubkey_b64
            platform_key_id = row.platform_sign_key_id

            export = await _build_export(
                session_b,
                tenant_id=tenant_id,
                scope_start=scope_start,
                scope_end=scope_end,
            )

            # Optional platform signature (CP9.34).
            if platform_key_id is not None and platform_signing_key is not None:
                export = sign_ma_diligence_export(
                    export,
                    platform_private_key=platform_signing_key,
                    platform_key_id=platform_key_id,
                )

            # Optional encryption-at-rest (CP9.36). Output shape changes
            # from MaDiligenceExport JSON to CipherEnvelope JSON.
            result_payload = _serialise_result(
                export,
                encrypt_for_pubkey_b64=encrypt_pubkey_b64,
            )

            await mark_ma_export_job_running_to_completed(
                session_b, job_id, result_export=result_payload
            )
            await session_b.commit()

        _LOG.info("ma_export_job %s: completed", job_id)

    except Exception as exc:
        # Any failure during the work stage: open Session C and mark
        # the job failed with the str(exc). The repo layer truncates
        # at 2048 chars (CP9.43).
        _LOG.warning("ma_export_job %s: failed: %s", job_id, exc)
        try:
            async with sessionmaker() as session_c:
                await mark_ma_export_job_failed(
                    session_c, job_id, error_message=f"{type(exc).__name__}: {exc}"
                )
                await session_c.commit()
        except Exception as fail_exc:
            # If even Session C can't write a failed status (DB down, etc),
            # there's nothing more we can do. Log and bail. The job will
            # remain stuck in 'running' until a sweeper or operator
            # intervenes. We don't re-raise the original exception
            # because it's already lost; we surface the marker exception
            # so the caller knows the runner couldn't finalise.
            _LOG.exception(
                "ma_export_job %s: could not record failure status: %s",
                job_id,
                fail_exc,
            )
            raise MaExportRunnerError(
                f"ma export job {job_id} could not be marked failed: {fail_exc}"
            ) from fail_exc


async def _build_export(
    session: Any,
    *,
    tenant_id: UUID,
    scope_start: datetime,
    scope_end: datetime,
) -> MaDiligenceExport:
    """Compose the MaDiligenceExport from anchors + receipts in scope.

    Mirrors the route layer's pipeline so the async-job result is
    byte-for-byte equivalent (modulo generated_at + export_id which
    are fresh per build) to what the synchronous route would have
    produced for the same window.

    Raises MaExportError on any validation failure (window too wide,
    too many anchors, etc.). The runner catches this and routes it
    to mark_ma_export_job_failed.
    """
    # 1. Anchors in scope.
    anchors_stmt = (
        select(TimestampAnchorRow)
        .where(
            TimestampAnchorRow.tenant_id == tenant_id,
            TimestampAnchorRow.anchor_date >= scope_start,
            TimestampAnchorRow.anchor_date <= scope_end,
        )
        .order_by(TimestampAnchorRow.anchor_date.asc())
        .limit(_MAX_PACKS_PER_BUNDLE + 1)
    )
    anchor_result = await session.execute(anchors_stmt)
    anchor_rows = list(anchor_result.scalars().all())
    if len(anchor_rows) > _MAX_PACKS_PER_BUNDLE:
        raise MaExportError(
            f"scope window covers more than {_MAX_PACKS_PER_BUNDLE} anchored days; "
            "narrow the window"
        )

    anchor_proofs: list[AnchorEvidence] = []
    evidence_packs: list[EvidencePack] = []
    now = datetime.now(UTC)

    # 2. Per-anchor: one EvidencePack covering that day's slice of the
    #    scope window.
    for anchor_row in anchor_rows:
        anchor_evidence = AnchorEvidence.from_anchor_row(anchor_row)
        anchor_proofs.append(anchor_evidence)

        day_start = anchor_row.anchor_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        chunk_start = max(day_start, scope_start)
        chunk_end = min(day_end, scope_end)

        pairs = await list_receipts_with_snapshot_for_tenant(
            session,
            tenant_id,
            scope_start=chunk_start,
            scope_end=chunk_end,
            limit=_MAX_RECEIPTS_PER_PACK + 1,
        )
        if len(pairs) > _MAX_RECEIPTS_PER_PACK:
            raise MaExportError(
                f"day {anchor_row.anchor_date.date().isoformat()} contains more than "
                f"{_MAX_RECEIPTS_PER_PACK} receipts; narrow the window"
            )

        pack = build_evidence_pack(
            tenant_id=tenant_id,
            generated_at=now,
            scope_start=chunk_start,
            scope_end=chunk_end,
            receipts_with_snapshots=pairs,
            anchor=anchor_evidence,
        )
        evidence_packs.append(pack)

    # 3. Compose the sealed bundle.
    return build_ma_diligence_export(
        tenant_id=tenant_id,
        scope_start=scope_start,
        scope_end=scope_end,
        generated_at=now,
        evidence_packs=evidence_packs,
        anchor_proofs=anchor_proofs,
    )


def _serialise_result(
    export: MaDiligenceExport,
    *,
    encrypt_for_pubkey_b64: str | None,
) -> dict[str, Any]:
    """Serialise the export to the dict form that lands in result_export.

    Two shapes:
      - encryption OFF -> the MaDiligenceExport JSON dict directly
      - encryption ON  -> a CipherEnvelope JSON dict wrapping the
        canonical MaDiligenceExport JSON bytes

    Either way the returned dict is JSON-serialisable and round-trips
    through JSONB unmodified. The acquirer recognises which shape they
    received by looking for the "@type" alias: "forensa:MaDiligenceExport"
    vs "forensa:CipherEnvelope".

    Encoding details mirror the synchronous route (CP9.36):
      - URL-safe base64 (RFC 4648 section 5) for the recipient pubkey
      - trailing '=' padding optional
      - any decode / encrypt failure raises MaExportError so the
        runner's exception handler marks the job failed cleanly
    """
    if encrypt_for_pubkey_b64 is None:
        # IMPORTANT: model_dump(mode="json") does NOT base64-encode bytes
        # in Pydantic v2; it tries to UTF-8 decode them, which fails for
        # raw Ed25519 signature bytes (0x93 etc). Use model_dump_json()
        # which uses pydantic's JSON encoder (base64 strings for bytes
        # via the CP9.44 field_serializer added to MaDiligenceExport),
        # then json.loads() to recover the dict shape for JSONB storage.
        # The acquirer reads the dict back via model_validate which
        # base64-decodes the signature string back to bytes (via the
        # paired field_validator on MaDiligenceExport).
        result: dict[str, Any] = json.loads(export.model_dump_json(by_alias=True))
        return result

    # Add padding if missing (urlsafe-b64 may strip it).
    padded = encrypt_for_pubkey_b64 + "=" * (-len(encrypt_for_pubkey_b64) % 4)
    try:
        recipient_public_key = base64.urlsafe_b64decode(padded)
    except (ValueError, base64.binascii.Error) as exc:  # type: ignore[attr-defined]
        raise MaExportError(f"encrypt_for_pubkey_b64 is not valid base64: {exc}") from exc

    plaintext = export.model_dump_json(by_alias=True).encode("utf-8")
    try:
        envelope = encrypt_for_recipient(plaintext, recipient_public_key=recipient_public_key)
    except EncryptError as exc:
        raise MaExportError(f"encryption failed: {exc}") from exc
    except MaExportSignatureError:  # pragma: no cover
        # Defensive: encrypt_for_recipient does not raise this, but
        # belt-and-braces against any future refactor.
        raise

    # Same bytes-as-base64 reasoning as above: model_dump_json -> json.loads
    # so any future bytes-typed field on CipherEnvelope round-trips.
    envelope_dict: dict[str, Any] = json.loads(envelope.model_dump_json(by_alias=True))
    return envelope_dict

"""packages.ledger.anchor - daily RFC 3161 timestamp anchoring (CP9.19 / BR-06).

Closes the Enterprise-Grade Review 3.10 finding: "BR-06 says Merkle-chained
ledger with RFC 3161 TSA. Today signed_at is server clock; a regulator at
T+1 year can't prove the server clock wasn't set wrong."

The anchoring contract
----------------------

For each ``(tenant_id, day)`` pair:

1. Find the latest ``Receipt.receipt_hash`` whose ``signed_at`` falls within
   ``[day 00:00:00 UTC, day 23:59:59.999999 UTC]``. This is the day's chain
   root - any earlier receipt that day is provably included via the
   linked-hash chain (each receipt binds ``prev_receipt_hash``).
2. Submit the root_hash to the configured ``TimestampClient``.
3. On success: persist a ``TimestampAnchorRow`` with status='anchored',
   the TSR bytes, the TSA's signature, and ``timestamped_at``.
4. On TSA failure: persist a tombstone row with status='deferred',
   ``root_hash=None``, ``tsr_bytes=None``. The next anchor run for the
   same (tenant_id, day) replaces the tombstone with a real anchor.
5. If no receipts exist for the tenant on the day: persist a tombstone
   with status='deferred' and the comment "no receipts to anchor" - this
   is data, not failure.

The ``anchor_day`` function is the entrypoint. Production wiring is a
daily cron job that iterates active tenants and calls ``anchor_day``
for each. The hackathon demo: ``scripts/anchor_today.py``.

Verification
------------

Given a regulator with a Receipt and a TimestampAnchorRow:

- ``verify_receipt_anchored_in(receipt, anchor, all_intermediate_receipts)``
  returns True iff:
  - The anchor's ``status == 'anchored'``
  - The anchor's ``timestamped_at`` is on or after ``receipt.signed_at``
  - There is a chain ``receipt.receipt_hash -> next.prev_receipt_hash -> ... -> anchor.root_hash``
    through ``all_intermediate_receipts``
  - The TSA's signature on the anchor verifies under the TSA's public key
    (verified separately via ``packages.crypto.tsa.verify_timestamp_response``).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, time
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.crypto.tsa import TimestampClient, TimestampClientError
from packages.ledger.models import ReceiptRow, TimestampAnchorRow
from packages.schema.receipt import Receipt

logger = logging.getLogger(__name__)

__all__ = [
    "AnchorAlreadyExistsError",
    "AnchorResult",
    "anchor_day",
    "get_anchor_for_day",
    "verify_receipt_anchored_in",
]


class AnchorAlreadyExistsError(Exception):
    """Raised when an anchored (not deferred) row already exists for the pair.

    The application layer treats this as "skip; nothing to do today" rather
    than "fail loudly" - re-running the daily job is idempotent for already-
    anchored days.
    """


@dataclass(frozen=True, slots=True)
class AnchorResult:
    """Outcome of an anchor_day call.

    Attributes
    ----------
    anchor_id : UUID
        The id of the persisted ``TimestampAnchorRow``.
    status : str
        'anchored' or 'deferred'.
    root_hash : str | None
        The day's chain root, or None if status='deferred'.
    timestamped_at : datetime | None
        The TSA's witnessed timestamp, or None if status='deferred'.
    receipts_covered : int
        Number of Receipts whose signed_at fell within the anchor's day.
        Zero for deferred-no-receipts; >=1 for anchored.
    """

    anchor_id: UUID
    status: str
    root_hash: str | None
    timestamped_at: datetime | None
    receipts_covered: int


def _day_bounds(day: datetime) -> tuple[datetime, datetime]:
    """Return ``(start, end)`` of the UTC day containing ``day``.

    ``day`` must be timezone-aware. ``start`` is the 00:00:00 UTC of that
    calendar date; ``end`` is 23:59:59.999999 UTC of the same date.
    """
    if day.tzinfo is None:
        raise ValueError("day must be timezone-aware")
    date_part = day.astimezone(UTC).date()
    start = datetime.combine(date_part, time.min, tzinfo=UTC)
    end = datetime.combine(date_part, time.max, tzinfo=UTC)
    return start, end


def _normalised_anchor_date(day: datetime) -> datetime:
    """The (tenant_id, anchor_date) key value: UTC midnight of the day."""
    start, _ = _day_bounds(day)
    return start


async def anchor_day(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    day: datetime,
    timestamp_client: TimestampClient,
    tsa_identifier: str | None = None,
) -> AnchorResult:
    """Anchor a tenant's chain for one UTC day.

    Idempotent on success: if an anchored (status='anchored') row already
    exists for (tenant_id, day), raises ``AnchorAlreadyExistsError`` so
    callers can choose to skip or replay.

    If a deferred tombstone exists, this call removes it and writes a fresh
    row reflecting today's outcome (anchored if TSA succeeds, deferred
    again if not).

    On TSA failure (any ``TimestampClientError``), persists a deferred
    tombstone and returns; does NOT propagate the exception. The caller
    inspects ``AnchorResult.status``.

    Parameters
    ----------
    session : AsyncSession
        Caller-controlled session. Anchor row is added via session.add +
        session.flush; the caller's session_scope decides commit boundary.
    tenant_id : UUID
        The tenant whose chain to anchor.
    day : datetime
        Any tz-aware datetime within the target UTC day. Internally
        normalised to UTC midnight of that day.
    timestamp_client : TimestampClient
        Production: ``Rfc3161TimestampClient``. Hackathon/test:
        ``MockTimestampClient``.
    tsa_identifier : str | None
        Override of the TSA identifier persisted on the row. When None,
        falls back to the client's identifier (MockTimestampClient
        exposes one; Rfc3161TimestampClient uses its endpoint URL).
    """
    anchor_date = _normalised_anchor_date(day)
    day_start, day_end = _day_bounds(day)

    # 1. Look up any existing row for (tenant_id, anchor_date).
    existing = await _get_existing_row(session, tenant_id, anchor_date)
    if existing is not None and existing.status == "anchored":
        raise AnchorAlreadyExistsError(
            f"Anchor already exists for tenant {tenant_id} on {anchor_date.date()}"
        )

    # 2. Find the day's latest receipt for this tenant.
    latest_receipt = await _get_latest_receipt_for_day(session, tenant_id, day_start, day_end)

    # 3a. No receipts on the day -> deferred-empty tombstone (replace
    # any existing tombstone in the same transaction).
    if latest_receipt is None:
        identifier = tsa_identifier or _client_identifier(timestamp_client)
        if existing is not None:
            await session.delete(existing)
            await session.flush()
        row = TimestampAnchorRow(
            id=uuid4(),
            tenant_id=tenant_id,
            anchor_date=anchor_date,
            root_hash=None,
            tsa_identifier=identifier,
            tsr_bytes=None,
            tsa_signature=None,
            timestamped_at=None,
            anchored_at=datetime.now(UTC),
            status="deferred",
        )
        session.add(row)
        await session.flush()
        logger.info(
            "forensa.anchor.deferred_empty",
            extra={
                "tenant_id": str(tenant_id),
                "anchor_date": anchor_date.date().isoformat(),
            },
        )
        return AnchorResult(
            anchor_id=row.id,
            status="deferred",
            root_hash=None,
            timestamped_at=None,
            receipts_covered=0,
        )

    # 3b. Receipts exist: try the TSA.
    root_hash = latest_receipt.receipt_hash
    try:
        tsa_response = await timestamp_client.request_timestamp(root_hash)
    except TimestampClientError as exc:
        logger.warning(
            "forensa.anchor.deferred_tsa_unavailable",
            extra={
                "tenant_id": str(tenant_id),
                "anchor_date": anchor_date.date().isoformat(),
                "root_hash": root_hash,
                "error": str(exc),
            },
        )
        identifier = tsa_identifier or _client_identifier(timestamp_client)
        if existing is not None:
            await session.delete(existing)
            await session.flush()
        row = TimestampAnchorRow(
            id=uuid4(),
            tenant_id=tenant_id,
            anchor_date=anchor_date,
            root_hash=None,
            tsa_identifier=identifier,
            tsr_bytes=None,
            tsa_signature=None,
            timestamped_at=None,
            anchored_at=datetime.now(UTC),
            status="deferred",
        )
        session.add(row)
        await session.flush()
        return AnchorResult(
            anchor_id=row.id,
            status="deferred",
            root_hash=None,
            timestamped_at=None,
            receipts_covered=await _count_receipts_for_day(session, tenant_id, day_start, day_end),
        )

    # 4. TSA returned a valid response. Persist.
    identifier = tsa_identifier or tsa_response.tsa_identifier
    if existing is not None:
        await session.delete(existing)
        await session.flush()
    row = TimestampAnchorRow(
        id=uuid4(),
        tenant_id=tenant_id,
        anchor_date=anchor_date,
        root_hash=root_hash,
        tsa_identifier=identifier,
        tsr_bytes=tsa_response.tsr_bytes,
        tsa_signature=tsa_response.signature,
        timestamped_at=tsa_response.timestamped_at,
        anchored_at=datetime.now(UTC),
        status="anchored",
    )
    session.add(row)
    await session.flush()
    receipts_covered = await _count_receipts_for_day(session, tenant_id, day_start, day_end)
    logger.info(
        "forensa.anchor.anchored",
        extra={
            "tenant_id": str(tenant_id),
            "anchor_date": anchor_date.date().isoformat(),
            "root_hash": root_hash,
            "tsa_identifier": identifier,
            "receipts_covered": receipts_covered,
        },
    )
    return AnchorResult(
        anchor_id=row.id,
        status="anchored",
        root_hash=root_hash,
        timestamped_at=tsa_response.timestamped_at,
        receipts_covered=receipts_covered,
    )


async def get_anchor_for_day(
    session: AsyncSession, *, tenant_id: UUID, day: datetime
) -> TimestampAnchorRow | None:
    """Return the anchor row for (tenant_id, day) or None if absent."""
    anchor_date = _normalised_anchor_date(day)
    return await _get_existing_row(session, tenant_id, anchor_date)


async def _get_existing_row(
    session: AsyncSession, tenant_id: UUID, anchor_date: datetime
) -> TimestampAnchorRow | None:
    stmt = select(TimestampAnchorRow).where(
        TimestampAnchorRow.tenant_id == tenant_id,
        TimestampAnchorRow.anchor_date == anchor_date,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _get_latest_receipt_for_day(
    session: AsyncSession,
    tenant_id: UUID,
    day_start: datetime,
    day_end: datetime,
) -> ReceiptRow | None:
    stmt = (
        select(ReceiptRow)
        .where(
            ReceiptRow.tenant_id == tenant_id,
            ReceiptRow.signed_at >= day_start,
            ReceiptRow.signed_at <= day_end,
        )
        .order_by(ReceiptRow.sequence.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _count_receipts_for_day(
    session: AsyncSession,
    tenant_id: UUID,
    day_start: datetime,
    day_end: datetime,
) -> int:
    from sqlalchemy import func

    stmt = select(func.count()).where(
        ReceiptRow.tenant_id == tenant_id,
        ReceiptRow.signed_at >= day_start,
        ReceiptRow.signed_at <= day_end,
    )
    result = await session.execute(stmt)
    return int(result.scalar_one() or 0)


def _client_identifier(client: TimestampClient) -> str:
    """Best-effort TSA identifier from the client. MockTimestampClient exposes
    one; Rfc3161TimestampClient exposes endpoint_url."""
    identifier = getattr(client, "identifier", None)
    if isinstance(identifier, str):
        return identifier
    endpoint = getattr(client, "endpoint_url", None)
    if isinstance(endpoint, str):
        return endpoint
    return "unknown"


def verify_receipt_anchored_in(
    receipt: Receipt,
    anchor: TimestampAnchorRow,
    intermediate_receipts: list[Receipt],
) -> bool:
    """Verify ``receipt`` is provably anchored by ``anchor``.

    Returns True iff ALL hold:

    1. ``anchor.status == 'anchored'``
    2. ``anchor.root_hash is not None`` and ``anchor.timestamped_at is not None``
    3. ``receipt.signed_at <= anchor.timestamped_at`` (the receipt was issued
       on or before the TSA's witness time)
    4. ``receipt.tenant_id == anchor.tenant_id``
    5. There's an unbroken chain from ``receipt.receipt_hash`` through
       ``intermediate_receipts`` to ``anchor.root_hash``. Each
       ``intermediate_receipts[i].prev_receipt_hash`` must equal the
       previous receipt's ``receipt_hash``, in order. The first
       intermediate's prev_receipt_hash must equal ``receipt.receipt_hash``;
       the last intermediate's receipt_hash must equal ``anchor.root_hash``.
       An empty ``intermediate_receipts`` list is valid iff
       ``receipt.receipt_hash == anchor.root_hash``.

    Non-raising: returns False on any check failure including malformed
    inputs.
    """
    if anchor.status != "anchored":
        return False
    if anchor.root_hash is None or anchor.timestamped_at is None:
        return False
    if receipt.signed_at > anchor.timestamped_at:
        return False
    if receipt.tenant_id != anchor.tenant_id:
        return False

    # Chain walk.
    if not intermediate_receipts:
        return receipt.receipt_hash == anchor.root_hash

    # First intermediate must link to receipt.
    if intermediate_receipts[0].prev_receipt_hash != receipt.receipt_hash:
        return False
    # Sequential link check.
    for i in range(1, len(intermediate_receipts)):
        if intermediate_receipts[i].prev_receipt_hash != intermediate_receipts[i - 1].receipt_hash:
            return False
    # Last intermediate must equal the anchor root.
    return intermediate_receipts[-1].receipt_hash == anchor.root_hash

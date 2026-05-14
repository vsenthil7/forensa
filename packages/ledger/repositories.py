"""Repository layer for the Forensa evidence ledger.

write_event_with_receipt is the single point of truth for ingesting one
event. It performs three INSERTs as a single atomic unit:

    1. INSERT INTO policy_snapshots ...
    2. INSERT INTO events ...
    3. INSERT INTO receipts ...  (with FKs to both above)

All three rows must succeed together or roll back together. The caller
holds the session and the transaction (session_scope from packages.ledger
.session); this function just stages the inserts and flushes.

It does NOT compute the Receipt: the caller passes in the already-built
Receipt from packages.ledger.receipt_builder.build_receipt. This keeps the
repository a pure persistence layer.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.ledger.models import EventRow, PolicySnapshotRow, ReceiptRow
from packages.policy.snapshot import PolicySnapshot
from packages.schema.event import Event
from packages.schema.receipt import Receipt


async def write_event_with_receipt(
    session: AsyncSession,
    *,
    event: Event,
    snapshot: PolicySnapshot,
    receipt: Receipt,
    snapshot_id: UUID | None = None,
) -> UUID:
    """Atomically persist (PolicySnapshot, Event, Receipt) and return the snapshot id.

    Insert order: snapshot -> event -> receipt (FK-respecting). All three
    rows are added to the session; the caller's session_scope commits.

    The receipt's policy_bundle_id must equal snapshot.policy_bundle_id.
    The receipt's tenant_id must equal event.tenant_id. Both invariants are
    asserted here to fail fast before any rows hit the DB.

    ``snapshot_id`` is the freshly-allocated UUID for the new
    ``policy_snapshots`` row. Callers that need to bind the snapshot id into
    the Receipt's receipt_hash BEFORE persistence (the ingest service does)
    must allocate it themselves with ``uuid4()`` and pass it through; the
    default ``None`` triggers internal allocation for callers that don't
    care (legacy tests, scripts). [CP9.11]

    Returns the policy_snapshot id used so the caller can pass it to
    recompute_receipt_hash if it wants to verify before commit.
    """
    if receipt.policy_bundle_id != snapshot.policy_bundle_id:
        raise ValueError(
            "receipt.policy_bundle_id does not match snapshot.policy_bundle_id; "
            "refusing to persist an inconsistent triple"
        )
    if receipt.tenant_id != event.tenant_id:
        raise ValueError(
            "receipt.tenant_id does not match event.tenant_id; "
            "refusing to persist a cross-tenant triple"
        )
    if receipt.event_id != event.id:
        raise ValueError(
            "receipt.event_id does not match event.id; " "refusing to persist a misaligned triple"
        )

    if snapshot_id is None:
        snapshot_id = uuid4()

    snapshot_row = PolicySnapshotRow(
        id=snapshot_id,
        tenant_id=event.tenant_id,
        policy_bundle_id=snapshot.policy_bundle_id,
        policy_bundle_version=snapshot.policy_bundle_version,
        content_hash=snapshot.content_hash,
        captured_at=snapshot.captured_at,
        verdict_decision=snapshot.verdict_decision,
        verdict_reason=snapshot.verdict_reason,
    )

    event_row = EventRow(
        id=event.id,
        tenant_id=event.tenant_id,
        agent_id=event.agent_id,
        trace_id=event.trace_id,
        span_id=event.span_id,
        parent_span_id=event.parent_span_id,
        kind=event.kind.value if hasattr(event.kind, "value") else event.kind,
        occurred_at=event.occurred_at,
        payload=event.payload,
        reasoning=event.reasoning,
        output=event.output,
        policy_version=event.policy_version,
        policy_verdict=event.policy_verdict,
    )

    receipt_row = ReceiptRow(
        id=receipt.id,
        tenant_id=receipt.tenant_id,
        event_id=receipt.event_id,
        policy_bundle_id=receipt.policy_bundle_id,
        policy_snapshot_id=snapshot_id,
        sequence=receipt.sequence,
        prev_receipt_hash=receipt.prev_receipt_hash,
        payload_hash=receipt.payload_hash,
        receipt_hash=receipt.receipt_hash,
        signature=receipt.signature,
        agent_signature=receipt.agent_signature,
        signed_at=receipt.signed_at,
    )

    session.add(snapshot_row)
    session.add(event_row)
    session.add(receipt_row)
    await session.flush()

    return snapshot_id


async def get_receipt_by_id(
    session: AsyncSession,
    receipt_id: UUID,
) -> tuple[Receipt, UUID] | None:
    """Return (Receipt, policy_snapshot_id) for a receipt id, or None if not found.

    The policy_snapshot_id is returned alongside the Receipt because
    recompute_receipt_hash needs it to verify integrity, and Receipt itself
    does not carry that field (only policy_bundle_id).
    """
    stmt = select(ReceiptRow).where(ReceiptRow.id == receipt_id).limit(1)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        return None
    receipt = Receipt(
        id=row.id,
        tenant_id=row.tenant_id,
        event_id=row.event_id,
        policy_bundle_id=row.policy_bundle_id,
        sequence=row.sequence,
        prev_receipt_hash=row.prev_receipt_hash,
        payload_hash=row.payload_hash,
        receipt_hash=row.receipt_hash,
        signature=row.signature,
        agent_signature=row.agent_signature,
        signed_at=row.signed_at,
    )
    return receipt, row.policy_snapshot_id


async def list_receipts_for_tenant(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
    signed_after: datetime | None = None,
    signed_before: datetime | None = None,
) -> list[Receipt]:
    """Return a page of Receipts for a tenant, newest first by sequence DESC.

    Used by the console /receipts list view. Sorted by sequence DESC so the
    most recently issued Receipt is first; the (tenant_id, sequence) unique
    index makes this a cheap index scan.

    Optional ``signed_after`` / ``signed_before`` (CP9.12 / NEW-P9.8.4)
    filter the rows on ``signed_at`` via the indexed ``(tenant_id, signed_at)``
    index. Inclusive on both ends. ``None`` on either skips that bound.

    NOTE: Deep-offset pagination performs poorly past ~10K rows. New callers
    should prefer ``list_receipts_for_tenant_cursor`` which seeks on the
    indexed sequence column instead.
    """
    stmt = select(ReceiptRow).where(ReceiptRow.tenant_id == tenant_id)
    if signed_after is not None:
        stmt = stmt.where(ReceiptRow.signed_at >= signed_after)
    if signed_before is not None:
        stmt = stmt.where(ReceiptRow.signed_at <= signed_before)
    stmt = stmt.order_by(ReceiptRow.sequence.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        Receipt(
            id=row.id,
            tenant_id=row.tenant_id,
            event_id=row.event_id,
            policy_bundle_id=row.policy_bundle_id,
            sequence=row.sequence,
            prev_receipt_hash=row.prev_receipt_hash,
            payload_hash=row.payload_hash,
            receipt_hash=row.receipt_hash,
            signature=row.signature,
            agent_signature=row.agent_signature,
            signed_at=row.signed_at,
        )
        for row in rows
    ]


async def list_receipts_for_tenant_cursor(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    limit: int = 50,
    before_sequence: int | None = None,
    signed_after: datetime | None = None,
    signed_before: datetime | None = None,
) -> list[Receipt]:
    """Cursor-paginated receipt listing (CP9.7).

    Returns up to ``limit`` Receipts for ``tenant_id``, newest first by
    ``sequence`` DESC, seeking on the indexed ``sequence`` column instead of
    OFFSET. This is O(log N) per page regardless of how far the caller has
    paginated, vs OFFSET which is O(offset + limit) and degrades after ~10K
    rows.

    Pagination contract:

    - First page: ``before_sequence=None`` (or omitted) -> newest ``limit`` rows.
    - Subsequent pages: pass the smallest ``sequence`` seen on the previous
      page as ``before_sequence`` -> the next ``limit`` rows with
      ``sequence < before_sequence``.
    - Empty result -> end of stream.

    Optional ``signed_after`` / ``signed_before`` (CP9.12 / NEW-P9.8.4)
    filter rows on ``signed_at`` via the indexed ``(tenant_id, signed_at)``
    index. Inclusive on both ends. Combine freely with the ``before_sequence``
    cursor.

    The ``(tenant_id, sequence)`` UNIQUE index makes the seek a single
    index lookup; the row read is then bounded by ``limit``.
    """
    stmt = select(ReceiptRow).where(ReceiptRow.tenant_id == tenant_id)
    if before_sequence is not None:
        stmt = stmt.where(ReceiptRow.sequence < before_sequence)
    if signed_after is not None:
        stmt = stmt.where(ReceiptRow.signed_at >= signed_after)
    if signed_before is not None:
        stmt = stmt.where(ReceiptRow.signed_at <= signed_before)
    stmt = stmt.order_by(ReceiptRow.sequence.desc()).limit(limit)

    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        Receipt(
            id=row.id,
            tenant_id=row.tenant_id,
            event_id=row.event_id,
            policy_bundle_id=row.policy_bundle_id,
            sequence=row.sequence,
            prev_receipt_hash=row.prev_receipt_hash,
            payload_hash=row.payload_hash,
            receipt_hash=row.receipt_hash,
            signature=row.signature,
            agent_signature=row.agent_signature,
            signed_at=row.signed_at,
        )
        for row in rows
    ]


async def list_receipts_with_snapshot_for_tenant(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    scope_start: datetime,
    scope_end: datetime,
    limit: int,
) -> list[tuple[Receipt, UUID]]:
    """List Receipts + their snapshot_ids in one query (CP9.7 - kills N+1).

    Used by ``/v1/evidence-packs`` and ``/v1/narratives`` to assemble the
    ``(Receipt, policy_snapshot_id)`` pairs the evidence-pack builder needs.
    Previously these endpoints did:

        rows = list_receipts_for_tenant(...)
        for r in rows:
            found = await get_receipt_by_id(r.id)   # N+1!

    Now a single query returns all pairs already filtered by the signed_at
    window. ``limit`` is enforced server-side; the caller adds +1 if it
    needs to detect overflow.

    Both scope endpoints are inclusive. signed_at is indexed by
    ``(tenant_id, signed_at)`` via the alembic migration.
    """
    stmt = (
        select(ReceiptRow)
        .where(
            ReceiptRow.tenant_id == tenant_id,
            ReceiptRow.signed_at >= scope_start,
            ReceiptRow.signed_at <= scope_end,
        )
        .order_by(ReceiptRow.sequence.asc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        (
            Receipt(
                id=row.id,
                tenant_id=row.tenant_id,
                event_id=row.event_id,
                policy_bundle_id=row.policy_bundle_id,
                sequence=row.sequence,
                prev_receipt_hash=row.prev_receipt_hash,
                payload_hash=row.payload_hash,
                receipt_hash=row.receipt_hash,
                signature=row.signature,
                agent_signature=row.agent_signature,
                signed_at=row.signed_at,
            ),
            row.policy_snapshot_id,
        )
        for row in rows
    ]


async def get_latest_receipt_for_tenant(
    session: AsyncSession,
    tenant_id: UUID,
) -> Receipt | None:
    """Return the most recent Receipt (by sequence DESC) for a tenant, or None.

    Used by the ingest pipeline to fetch prev_receipt before building the
    next one. Single-query path with the (tenant_id, sequence) unique index.
    """
    stmt = (
        select(ReceiptRow)
        .where(ReceiptRow.tenant_id == tenant_id)
        .order_by(ReceiptRow.sequence.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return Receipt(
        id=row.id,
        tenant_id=row.tenant_id,
        event_id=row.event_id,
        policy_bundle_id=row.policy_bundle_id,
        sequence=row.sequence,
        prev_receipt_hash=row.prev_receipt_hash,
        payload_hash=row.payload_hash,
        receipt_hash=row.receipt_hash,
        signature=row.signature,
        agent_signature=row.agent_signature,
        signed_at=row.signed_at,
    )


# Suppress unused-import warning for datetime in __all__ helpers
_ = datetime, UTC

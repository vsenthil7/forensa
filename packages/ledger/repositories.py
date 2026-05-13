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
) -> UUID:
    """Atomically persist (PolicySnapshot, Event, Receipt) and return the snapshot id.

    Insert order: snapshot -> event -> receipt (FK-respecting). All three
    rows are added to the session; the caller's session_scope commits.

    The receipt's policy_bundle_id must equal snapshot.policy_bundle_id.
    The receipt's tenant_id must equal event.tenant_id. Both invariants are
    asserted here to fail fast before any rows hit the DB.

    Returns the freshly-created policy_snapshot id so the caller can pass it
    to recompute_receipt_hash if it wants to verify before commit.
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
        signed_at=receipt.signed_at,
    )

    session.add(snapshot_row)
    session.add(event_row)
    session.add(receipt_row)
    await session.flush()

    return snapshot_id


async def list_receipts_for_tenant(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[Receipt]:
    """Return a page of Receipts for a tenant, newest first by sequence DESC.

    Used by the console /receipts list view. Sorted by sequence DESC so the
    most recently issued Receipt is first; the (tenant_id, sequence) unique
    index makes this a cheap index scan.
    """
    from sqlalchemy import select

    stmt = (
        select(ReceiptRow)
        .where(ReceiptRow.tenant_id == tenant_id)
        .order_by(ReceiptRow.sequence.desc())
        .limit(limit)
        .offset(offset)
    )
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
            signed_at=row.signed_at,
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
    from sqlalchemy import select

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
        signed_at=row.signed_at,
    )


# Suppress unused-import warning for datetime in __all__ helpers
_ = datetime, UTC

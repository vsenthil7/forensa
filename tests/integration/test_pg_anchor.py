"""End-to-end TSA anchoring against real Postgres (CP9.19 / BR-06).

Closes the gap that unit tests with mocked sessions can't cover:

- The TimestampAnchorRow ORM model writes correctly to PostgreSQL 16
  (UUID, JSONB-style status enum, LargeBinary nullable columns,
  composite UNIQUE).
- anchor_day's actual SQL queries against the real backend honour the
  signed_at window filter and the sequence DESC ordering.
- The UNIQUE constraint on (tenant_id, anchor_date) is enforced at the
  DB level - we verify it by inserting a deferred row, then re-anchoring
  and confirming the old row was DELETEd before the new row was INSERTed
  (otherwise the UNIQUE would have raised).
- get_anchor_for_day round-trips the persisted row correctly.
- verify_receipt_anchored_in works against the persisted shape.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from packages.crypto.sign import generate_keypair
from packages.crypto.tsa import MockTimestampClient, verify_timestamp_response
from packages.ledger.anchor import (
    AnchorAlreadyExistsError,
    anchor_day,
    get_anchor_for_day,
    verify_receipt_anchored_in,
)
from packages.ledger.models import ReceiptRow, TimestampAnchorRow
from packages.ledger.receipt_builder import build_receipt
from packages.policy.bundle_builder import build_bundle
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.policy.snapshot import capture_snapshot
from packages.schema.receipt import Receipt

pytestmark = pytest.mark.pg


async def _seed_tenant_with_chain(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    n_receipts: int,
    signed_at_base: datetime,
) -> list[Receipt]:
    """Insert tenant + agent + bundle + snapshot + n receipts. Returns the
    in-memory Receipt list with hash-linked chain."""
    now = datetime.now(UTC)
    agent_id = uuid.uuid4()
    bundle_id = uuid.uuid4()
    snap_id = uuid.uuid4()

    # tenants
    await session.execute(
        text(
            "INSERT INTO tenants (id, slug, display_name, signing_key_id, created_at) "
            "VALUES (:id, :slug, :name, :kid, :now)"
        ),
        {
            "id": tenant_id,
            "slug": f"t-{tenant_id.hex[:8]}",
            "name": "Anchor Test Tenant",
            "kid": "kid-anchor-test",
            "now": now,
        },
    )
    # agents
    await session.execute(
        text(
            "INSERT INTO agents (id, tenant_id, slug, display_name, "
            "identity_public_key, status, created_at) "
            "VALUES (:id, :tid, :slug, :name, :pk, 'active', :now)"
        ),
        {
            "id": agent_id,
            "tid": tenant_id,
            "slug": f"a-{agent_id.hex[:8]}",
            "name": "Anchor Test Agent",
            "pk": b"\x00" * 32,
            "now": now,
        },
    )
    # bundle + snapshot
    bundle_content = {
        "rules": [{"kind": "x", "decision": "allow"}],
        "default": "allow",
    }
    bundle = build_bundle(tenant_id=tenant_id, version="1.0.0", content=bundle_content)
    # Force the bundle's id to match what we'll insert.
    bundle_obj = bundle.model_copy(update={"id": bundle_id})
    await session.execute(
        text(
            "INSERT INTO policy_bundles "
            "(id, tenant_id, version, content_hash, content, created_at, status) "
            "VALUES (:id, :tid, '1.0.0', :hash, CAST(:content AS jsonb), :now, 'active')"
        ),
        {
            "id": bundle_id,
            "tid": tenant_id,
            "hash": bundle_obj.content_hash,
            "content": '{"rules":[{"kind":"x","decision":"allow"}],"default":"allow"}',
            "now": now,
        },
    )
    mock_client = MockLobsterTrapClient(
        policy_bundle_id=bundle_id,
        policy_bundle_version=bundle_obj.version,
        content=bundle_content,
    )
    verdict = await mock_client.evaluate(tenant_id, {"kind": "x"})
    snap = capture_snapshot(bundle_obj, verdict)
    await session.execute(
        text(
            "INSERT INTO policy_snapshots (id, tenant_id, policy_bundle_id, "
            "policy_bundle_version, content_hash, captured_at, "
            "verdict_decision, verdict_reason) "
            "VALUES (:id, :tid, :bid, '1.0.0', :hash, :now, :dec, :reason)"
        ),
        {
            "id": snap_id,
            "tid": tenant_id,
            "bid": bundle_id,
            "hash": bundle_obj.content_hash,
            "now": now,
            "dec": verdict.decision.value,
            "reason": verdict.reason,
        },
    )

    # Build the in-memory chain.
    priv, _ = generate_keypair()
    receipts: list[Receipt] = []
    prev: Receipt | None = None
    for i in range(n_receipts):
        r = build_receipt(
            tenant_id=tenant_id,
            event_id=uuid.uuid4(),
            event_payload={"step": i},
            policy_snapshot=snap,
            policy_snapshot_id=snap_id,
            prev_receipt=prev,
            tenant_signing_key=priv,
        )
        r = r.model_copy(update={"signed_at": signed_at_base + timedelta(minutes=i)})
        receipts.append(r)
        prev = r

    # Persist each receipt + a placeholder event.
    for r in receipts:
        await session.execute(
            text(
                "INSERT INTO events (id, tenant_id, agent_id, trace_id, span_id, "
                "kind, occurred_at, payload) "
                "VALUES (:id, :tid, :aid, :trace, :span, 'tool_call', :now, "
                "CAST(:payload AS jsonb))"
            ),
            {
                "id": r.event_id,
                "tid": tenant_id,
                "aid": agent_id,
                "trace": "a" * 32,
                "span": "b" * 16,
                "now": r.signed_at,
                "payload": '{"step":' + str(receipts.index(r)) + "}",
            },
        )
        await session.execute(
            text(
                "INSERT INTO receipts (id, tenant_id, event_id, policy_bundle_id, "
                "policy_snapshot_id, sequence, prev_receipt_hash, payload_hash, "
                "receipt_hash, signature, signed_at) "
                "VALUES (:id, :tid, :eid, :bid, :sid, :seq, :prev, :ph, :rh, "
                ":sig, :now)"
            ),
            {
                "id": r.id,
                "tid": tenant_id,
                "eid": r.event_id,
                "bid": bundle_id,
                "sid": snap_id,
                "seq": r.sequence,
                "prev": r.prev_receipt_hash,
                "ph": r.payload_hash,
                "rh": r.receipt_hash,
                "sig": r.signature,
                "now": r.signed_at,
            },
        )
    await session.commit()
    return receipts


# ---------------------------------------------------------------------------
# Happy path: anchor a day with receipts
# ---------------------------------------------------------------------------


async def test_anchor_day_persists_anchored_row_against_real_pg(
    pg_clean_session: AsyncSession,
) -> None:
    """End-to-end: chain of 5 receipts written to PG, anchor_day produces
    a row with status='anchored', the latest receipt's hash as root, and
    the count of receipts covered."""
    tenant_id = uuid.uuid4()
    day = datetime(2026, 5, 15, 12, 0, tzinfo=UTC)
    receipts = await _seed_tenant_with_chain(
        pg_clean_session,
        tenant_id=tenant_id,
        n_receipts=5,
        signed_at_base=datetime(2026, 5, 15, 10, 0, tzinfo=UTC),
    )

    client = MockTimestampClient(identifier="pg-test-tsa")
    result = await anchor_day(
        pg_clean_session,
        tenant_id=tenant_id,
        day=day,
        timestamp_client=client,
    )
    await pg_clean_session.commit()

    assert result.status == "anchored"
    assert result.root_hash == receipts[-1].receipt_hash
    assert result.receipts_covered == 5
    assert result.timestamped_at is not None

    # Verify the row landed in the DB with the right shape.
    db_row = await pg_clean_session.execute(
        select(TimestampAnchorRow).where(TimestampAnchorRow.tenant_id == tenant_id)
    )
    row = db_row.scalar_one()
    assert row.status == "anchored"
    assert row.root_hash == receipts[-1].receipt_hash
    assert row.tsa_identifier == "pg-test-tsa"
    assert row.tsr_bytes is not None
    assert row.tsa_signature is not None
    assert len(row.tsa_signature) == 64
    assert row.timestamped_at is not None
    assert row.anchored_at is not None
    # anchor_date is UTC midnight of day.
    assert row.anchor_date == datetime(2026, 5, 15, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Receipt window filter
# ---------------------------------------------------------------------------


async def test_anchor_day_filters_receipts_outside_window(
    pg_clean_session: AsyncSession,
) -> None:
    """Receipts signed_at OUTSIDE the day MUST NOT be counted or used as the
    root. Verifies the WHERE signed_at >= day_start AND signed_at <= day_end
    clause is honoured by Postgres."""
    tenant_id = uuid.uuid4()
    # 5 receipts: 2 on 2026-05-14, 3 on 2026-05-15. Anchor 2026-05-15.
    receipts = await _seed_tenant_with_chain(
        pg_clean_session,
        tenant_id=tenant_id,
        n_receipts=5,
        # Base at 2026-05-14 22:30 UTC. With +1min steps:
        # [22:30, 22:31] are on 14th; [22:32 onwards] crosses into 15th... wait
        # that's not crossing midnight. Use larger step:
        signed_at_base=datetime(2026, 5, 14, 23, 0, tzinfo=UTC),
    )
    # All 5 are on 2026-05-14 (23:00 + i minutes). Recompute with hours:
    # Actually simpler: just re-write some of them via UPDATE.

    # Push 3 receipts to 2026-05-15 explicitly.
    for r in receipts[-3:]:
        new_signed_at = datetime(2026, 5, 15, 10, 0, tzinfo=UTC) + (
            r.signed_at - receipts[0].signed_at
        )
        await pg_clean_session.execute(
            text("UPDATE receipts SET signed_at = :ts WHERE id = :id"),
            {"ts": new_signed_at, "id": r.id},
        )
    await pg_clean_session.commit()

    day = datetime(2026, 5, 15, 12, tzinfo=UTC)
    result = await anchor_day(
        pg_clean_session,
        tenant_id=tenant_id,
        day=day,
        timestamp_client=MockTimestampClient(),
    )
    await pg_clean_session.commit()

    assert result.status == "anchored"
    # Only 3 receipts on 2026-05-15. Root is the latest (highest sequence).
    assert result.receipts_covered == 3
    assert result.root_hash == receipts[-1].receipt_hash


# ---------------------------------------------------------------------------
# Empty day: deferred tombstone
# ---------------------------------------------------------------------------


async def test_anchor_day_persists_deferred_when_no_receipts(
    pg_clean_session: AsyncSession,
) -> None:
    """Tenant with no receipts on the day -> deferred tombstone row."""
    tenant_id = uuid.uuid4()
    # Seed only the tenant (and a fake bundle row through the helper with 0
    # receipts) - the helper doesn't add receipts when n_receipts=0.
    await _seed_tenant_with_chain(
        pg_clean_session,
        tenant_id=tenant_id,
        n_receipts=0,
        signed_at_base=datetime(2026, 5, 15, tzinfo=UTC),
    )

    result = await anchor_day(
        pg_clean_session,
        tenant_id=tenant_id,
        day=datetime(2026, 5, 15, tzinfo=UTC),
        timestamp_client=MockTimestampClient(),
    )
    await pg_clean_session.commit()

    assert result.status == "deferred"
    assert result.root_hash is None
    assert result.receipts_covered == 0

    row = (
        await pg_clean_session.execute(
            select(TimestampAnchorRow).where(TimestampAnchorRow.tenant_id == tenant_id)
        )
    ).scalar_one()
    assert row.status == "deferred"
    assert row.root_hash is None
    assert row.tsr_bytes is None
    assert row.tsa_signature is None
    assert row.timestamped_at is None
    # tsa_identifier still populated (the client's identifier).
    assert row.tsa_identifier == "forensa-mock-2026"


# ---------------------------------------------------------------------------
# UNIQUE constraint enforced + idempotency for anchored days
# ---------------------------------------------------------------------------


async def test_anchor_day_refuses_to_reanchor_already_anchored_day(
    pg_clean_session: AsyncSession,
) -> None:
    """Already-anchored (tenant, day) -> AnchorAlreadyExistsError."""
    tenant_id = uuid.uuid4()
    await _seed_tenant_with_chain(
        pg_clean_session,
        tenant_id=tenant_id,
        n_receipts=2,
        signed_at_base=datetime(2026, 5, 15, 10, tzinfo=UTC),
    )
    client = MockTimestampClient()
    await anchor_day(
        pg_clean_session,
        tenant_id=tenant_id,
        day=datetime(2026, 5, 15, tzinfo=UTC),
        timestamp_client=client,
    )
    await pg_clean_session.commit()

    with pytest.raises(AnchorAlreadyExistsError):
        await anchor_day(
            pg_clean_session,
            tenant_id=tenant_id,
            day=datetime(2026, 5, 15, tzinfo=UTC),
            timestamp_client=client,
        )


async def test_anchor_day_replaces_deferred_tombstone_with_anchored(
    pg_clean_session: AsyncSession,
) -> None:
    """Deferred tombstone + retry -> deletes old, inserts new anchored row.

    Verifies the application-layer delete-then-insert pattern actually works
    against the UNIQUE constraint at the DB level. Simulates the
    "TSA was down on Monday, comes back Tuesday" reprocess flow.
    """
    tenant_id = uuid.uuid4()

    # Seed with 0 receipts so the first anchor_day writes a deferred tombstone.
    await _seed_tenant_with_chain(
        pg_clean_session,
        tenant_id=tenant_id,
        n_receipts=0,
        signed_at_base=datetime(2026, 5, 15, tzinfo=UTC),
    )
    first = await anchor_day(
        pg_clean_session,
        tenant_id=tenant_id,
        day=datetime(2026, 5, 15, tzinfo=UTC),
        timestamp_client=MockTimestampClient(),
    )
    await pg_clean_session.commit()
    assert first.status == "deferred"
    deferred_anchor_id = first.anchor_id

    # Now write 2 receipts FOR THIS SAME tenant - reusing the already-seeded
    # bundle + snapshot by fetching them rather than re-seeding (which would
    # collide on uq_policy_bundles_tenant_version).
    bundle_id_row = (
        await pg_clean_session.execute(
            text("SELECT id, content_hash FROM policy_bundles " "WHERE tenant_id = :tid LIMIT 1"),
            {"tid": tenant_id},
        )
    ).first()
    assert bundle_id_row is not None
    bundle_id = bundle_id_row[0]
    bundle_hash = bundle_id_row[1]
    snap_id_row = (
        await pg_clean_session.execute(
            text("SELECT id FROM policy_snapshots WHERE tenant_id = :tid LIMIT 1"),
            {"tid": tenant_id},
        )
    ).first()
    assert snap_id_row is not None
    snap_id = snap_id_row[0]
    agent_id_row = (
        await pg_clean_session.execute(
            text("SELECT id FROM agents WHERE tenant_id = :tid LIMIT 1"),
            {"tid": tenant_id},
        )
    ).first()
    assert agent_id_row is not None
    agent_id = agent_id_row[0]

    # Build + persist a 2-receipt chain directly.
    bundle_content = {
        "rules": [{"kind": "x", "decision": "allow"}],
        "default": "allow",
    }
    bundle = build_bundle(tenant_id=tenant_id, version="1.0.0", content=bundle_content)
    bundle = bundle.model_copy(update={"id": bundle_id, "content_hash": bundle_hash})
    mock_client = MockLobsterTrapClient(
        policy_bundle_id=bundle_id,
        policy_bundle_version="1.0.0",
        content=bundle_content,
    )
    verdict = await mock_client.evaluate(tenant_id, {"kind": "x"})
    snap = capture_snapshot(bundle, verdict)
    priv, _ = generate_keypair()
    receipts: list[Receipt] = []
    prev: Receipt | None = None
    base = datetime(2026, 5, 15, 10, tzinfo=UTC)
    for i in range(2):
        r = build_receipt(
            tenant_id=tenant_id,
            event_id=uuid.uuid4(),
            event_payload={"step": i},
            policy_snapshot=snap,
            policy_snapshot_id=snap_id,
            prev_receipt=prev,
            tenant_signing_key=priv,
        )
        r = r.model_copy(update={"signed_at": base + timedelta(minutes=i)})
        receipts.append(r)
        prev = r
        await pg_clean_session.execute(
            text(
                "INSERT INTO events (id, tenant_id, agent_id, trace_id, span_id, "
                "kind, occurred_at, payload) "
                "VALUES (:id, :tid, :aid, :trace, :span, 'tool_call', :now, "
                "CAST(:payload AS jsonb))"
            ),
            {
                "id": r.event_id,
                "tid": tenant_id,
                "aid": agent_id,
                "trace": "a" * 32,
                "span": "b" * 16,
                "now": r.signed_at,
                "payload": '{"step":' + str(i) + "}",
            },
        )
        await pg_clean_session.execute(
            text(
                "INSERT INTO receipts (id, tenant_id, event_id, policy_bundle_id, "
                "policy_snapshot_id, sequence, prev_receipt_hash, payload_hash, "
                "receipt_hash, signature, signed_at) "
                "VALUES (:id, :tid, :eid, :bid, :sid, :seq, :prev, :ph, :rh, "
                ":sig, :now)"
            ),
            {
                "id": r.id,
                "tid": tenant_id,
                "eid": r.event_id,
                "bid": bundle_id,
                "sid": snap_id,
                "seq": r.sequence,
                "prev": r.prev_receipt_hash,
                "ph": r.payload_hash,
                "rh": r.receipt_hash,
                "sig": r.signature,
                "now": r.signed_at,
            },
        )
    await pg_clean_session.commit()

    # Now re-anchor. The deferred tombstone must be replaced.
    result = await anchor_day(
        pg_clean_session,
        tenant_id=tenant_id,
        day=datetime(2026, 5, 15, tzinfo=UTC),
        timestamp_client=MockTimestampClient(),
    )
    await pg_clean_session.commit()

    assert result.status == "anchored"
    # Exactly one row should exist (the new one replaced the tombstone).
    rows = (
        (
            await pg_clean_session.execute(
                select(TimestampAnchorRow).where(TimestampAnchorRow.tenant_id == tenant_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].status == "anchored"
    # The new anchor row has a DIFFERENT id from the deferred one.
    assert rows[0].id != deferred_anchor_id


# ---------------------------------------------------------------------------
# get_anchor_for_day round-trip
# ---------------------------------------------------------------------------


async def test_get_anchor_for_day_round_trip(
    pg_clean_session: AsyncSession,
) -> None:
    """Persisted row round-trips correctly via get_anchor_for_day."""
    tenant_id = uuid.uuid4()
    await _seed_tenant_with_chain(
        pg_clean_session,
        tenant_id=tenant_id,
        n_receipts=1,
        signed_at_base=datetime(2026, 5, 15, 10, tzinfo=UTC),
    )
    written = await anchor_day(
        pg_clean_session,
        tenant_id=tenant_id,
        day=datetime(2026, 5, 15, tzinfo=UTC),
        timestamp_client=MockTimestampClient(identifier="round-trip-tsa"),
    )
    await pg_clean_session.commit()

    fetched = await get_anchor_for_day(
        pg_clean_session,
        tenant_id=tenant_id,
        day=datetime(2026, 5, 15, 23, tzinfo=UTC),
    )
    assert fetched is not None
    assert fetched.id == written.anchor_id
    assert fetched.status == "anchored"
    assert fetched.tsa_identifier == "round-trip-tsa"


async def test_get_anchor_for_day_returns_none_for_missing_day(
    pg_clean_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    await _seed_tenant_with_chain(
        pg_clean_session,
        tenant_id=tenant_id,
        n_receipts=0,
        signed_at_base=datetime(2026, 5, 15, tzinfo=UTC),
    )
    result = await get_anchor_for_day(
        pg_clean_session,
        tenant_id=tenant_id,
        day=datetime(2026, 5, 15, tzinfo=UTC),
    )
    assert result is None


# ---------------------------------------------------------------------------
# End-to-end: receipt -> anchor -> regulator verification
# ---------------------------------------------------------------------------


async def test_end_to_end_receipt_provably_anchored(
    pg_clean_session: AsyncSession,
) -> None:
    """Regulator scenario: given a Receipt and an anchored row, verify both:

    1. The TSA's signature verifies under the TSA's public key.
    2. The receipt is provably in the chain rooted at anchor.root_hash.

    Receipts are signed at a PAST date so the anchor's timestamped_at
    (= datetime.now(UTC) at test runtime) is strictly after every receipt's
    signed_at - the causality check in verify_receipt_anchored_in.
    """
    tenant_id = uuid.uuid4()
    receipts = await _seed_tenant_with_chain(
        pg_clean_session,
        tenant_id=tenant_id,
        n_receipts=3,
        signed_at_base=datetime(2026, 5, 14, 10, 0, tzinfo=UTC),
    )
    client = MockTimestampClient(identifier="reg-test-tsa")
    await anchor_day(
        pg_clean_session,
        tenant_id=tenant_id,
        day=datetime(2026, 5, 14, tzinfo=UTC),
        timestamp_client=client,
    )
    await pg_clean_session.commit()

    # Reload the anchor row.
    anchor = (
        await pg_clean_session.execute(
            select(TimestampAnchorRow).where(TimestampAnchorRow.tenant_id == tenant_id)
        )
    ).scalar_one()

    # 1. The TSA signature verifies. We need to reconstruct the TimestampResponse
    # from the persisted row. The mock client's public key is needed to verify.
    # Real regulators get the public key out-of-band; in this test we hold it.
    from packages.crypto.tsa import TimestampResponse

    response = TimestampResponse(
        tsa_identifier=anchor.tsa_identifier,
        tsr_bytes=bytes(anchor.tsr_bytes),
        timestamped_at=anchor.timestamped_at,
        hashed_root=anchor.root_hash,
        signature=bytes(anchor.tsa_signature),
    )
    assert verify_timestamp_response(response, tsa_public_key=client.public_key)

    # 2. receipts[0] is provably anchored by chain-walk through [1, 2].
    # Re-fetch receipts from DB to ensure the persisted shape matches.
    db_receipts = (
        (
            await pg_clean_session.execute(
                select(ReceiptRow)
                .where(ReceiptRow.tenant_id == tenant_id)
                .order_by(ReceiptRow.sequence.asc())
            )
        )
        .scalars()
        .all()
    )
    assert len(db_receipts) == 3
    # Pydantic-reconstruct from rows. Use the same fields as the row.
    reconstructed: list[Receipt] = []
    for row in db_receipts:
        reconstructed.append(
            Receipt(
                id=row.id,
                tenant_id=row.tenant_id,
                event_id=row.event_id,
                policy_bundle_id=row.policy_bundle_id,
                sequence=row.sequence,
                prev_receipt_hash=row.prev_receipt_hash,
                payload_hash=row.payload_hash,
                receipt_hash=row.receipt_hash,
                signature=bytes(row.signature),
                signed_at=row.signed_at,
            )
        )

    assert verify_receipt_anchored_in(
        reconstructed[0], anchor, intermediate_receipts=reconstructed[1:]
    )
    # Also: the LAST receipt is itself the root (no intermediates).
    assert verify_receipt_anchored_in(reconstructed[-1], anchor, intermediate_receipts=[])
    # The original in-memory receipts also work (round-trip preserves hash).
    assert verify_receipt_anchored_in(receipts[0], anchor, intermediate_receipts=receipts[1:])

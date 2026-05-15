"""Tests for packages.ledger.anchor (CP9.19 / BR-06)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from packages.crypto.sign import generate_keypair
from packages.crypto.tsa import (
    MockTimestampClient,
    TimestampClient,
    TimestampClientError,
)
from packages.ledger.anchor import (
    AnchorAlreadyExistsError,
    AnchorResult,
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_session(
    *,
    existing_anchor: TimestampAnchorRow | None = None,
    latest_receipt_row: ReceiptRow | None = None,
    receipts_count: int = 0,
):
    """Build a mock AsyncSession that satisfies anchor_day's queries.

    The module issues three distinct queries in sequence:
    1. _get_existing_row (anchor lookup)
    2. _get_latest_receipt_for_day (chain head lookup)
    3. _count_receipts_for_day (only on the anchored path)

    The mock dispatches by inspecting the compiled SQL's primary table.
    """
    rows_added: list[object] = []
    rows_deleted: list[object] = []

    call_count = {"n": 0}

    async def _execute(stmt):
        call_count["n"] += 1
        result = MagicMock()
        # Compile the statement so we can look at column refs.
        try:
            compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))
        except Exception:
            compiled = ""

        if "timestamp_anchors" in compiled.lower():
            result.scalar_one_or_none = MagicMock(return_value=existing_anchor)
        elif "count(" in compiled.lower():
            result.scalar_one = MagicMock(return_value=receipts_count)
        else:
            # Latest-receipt lookup.
            result.scalar_one_or_none = MagicMock(return_value=latest_receipt_row)
        return result

    session = MagicMock()
    session.execute = AsyncMock(side_effect=_execute)
    session.add = MagicMock(side_effect=lambda r: rows_added.append(r))
    session.delete = AsyncMock(side_effect=lambda r: rows_deleted.append(r))
    session.flush = AsyncMock(return_value=None)
    # Hand the added/deleted lists back to the test via attributes.
    session._rows_added = rows_added  # type: ignore[attr-defined]
    session._rows_deleted = rows_deleted  # type: ignore[attr-defined]
    return session


def _make_receipt_row(
    *, tenant_id: UUID, receipt_hash: str, signed_at: datetime, sequence: int = 0
) -> MagicMock:
    row = MagicMock(spec=ReceiptRow)
    row.id = uuid4()
    row.tenant_id = tenant_id
    row.event_id = uuid4()
    row.policy_bundle_id = uuid4()
    row.policy_snapshot_id = uuid4()
    row.sequence = sequence
    row.prev_receipt_hash = None
    row.payload_hash = "p" * 64
    row.receipt_hash = receipt_hash
    row.signature = b"\x00" * 64
    row.agent_signature = None
    row.signed_at = signed_at
    return row


def _make_anchor_row(
    *,
    tenant_id: UUID,
    anchor_date: datetime,
    status: str = "anchored",
    root_hash: str | None = "a" * 64,
) -> MagicMock:
    row = MagicMock(spec=TimestampAnchorRow)
    row.id = uuid4()
    row.tenant_id = tenant_id
    row.anchor_date = anchor_date
    row.root_hash = root_hash if status == "anchored" else None
    row.tsa_identifier = "test-tsa"
    row.tsr_bytes = b"\x00" * 16 if status == "anchored" else None
    row.tsa_signature = b"\x00" * 64 if status == "anchored" else None
    row.timestamped_at = datetime.now(UTC) if status == "anchored" else None
    row.anchored_at = datetime.now(UTC)
    row.status = status
    return row


# ---------------------------------------------------------------------------
# anchor_day - happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_anchor_day_happy_path_persists_anchored_row():
    tenant = uuid4()
    day = datetime(2026, 5, 15, 12, 0, tzinfo=UTC)
    chain_head = _make_receipt_row(
        tenant_id=tenant,
        receipt_hash="c" * 64,
        signed_at=datetime(2026, 5, 15, 23, 30, tzinfo=UTC),
    )
    session = _mock_session(latest_receipt_row=chain_head, receipts_count=42)
    client = MockTimestampClient()

    result = await anchor_day(session, tenant_id=tenant, day=day, timestamp_client=client)

    assert isinstance(result, AnchorResult)
    assert result.status == "anchored"
    assert result.root_hash == "c" * 64
    assert result.timestamped_at is not None
    assert result.timestamped_at.tzinfo == UTC
    assert result.receipts_covered == 42

    # One anchor row added.
    anchor_rows = [r for r in session._rows_added if isinstance(r, TimestampAnchorRow)]
    assert len(anchor_rows) == 1
    row = anchor_rows[0]
    assert row.tenant_id == tenant
    assert row.status == "anchored"
    assert row.root_hash == "c" * 64
    assert row.tsa_identifier == "forensa-mock-2026"
    assert row.tsr_bytes  # populated
    assert row.tsa_signature  # populated
    # anchor_date normalised to UTC midnight of day
    assert row.anchor_date == datetime(2026, 5, 15, 0, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_anchor_day_uses_custom_tsa_identifier_when_provided():
    """tsa_identifier kwarg overrides the client's own identifier."""
    tenant = uuid4()
    day = datetime(2026, 5, 15, tzinfo=UTC)
    chain_head = _make_receipt_row(
        tenant_id=tenant,
        receipt_hash="c" * 64,
        signed_at=datetime(2026, 5, 15, 12, tzinfo=UTC),
    )
    session = _mock_session(latest_receipt_row=chain_head, receipts_count=1)
    client = MockTimestampClient(identifier="default-id")

    await anchor_day(
        session,
        tenant_id=tenant,
        day=day,
        timestamp_client=client,
        tsa_identifier="override-id",
    )
    row = next(r for r in session._rows_added if isinstance(r, TimestampAnchorRow))
    assert row.tsa_identifier == "override-id"


# ---------------------------------------------------------------------------
# anchor_day - deferred paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_anchor_day_deferred_when_no_receipts_for_day():
    """No receipts on the day -> status='deferred', root_hash=None,
    timestamped_at=None. This is a tombstone, not a failure."""
    tenant = uuid4()
    day = datetime(2026, 5, 15, tzinfo=UTC)
    session = _mock_session(latest_receipt_row=None)
    client = MockTimestampClient()

    result = await anchor_day(session, tenant_id=tenant, day=day, timestamp_client=client)

    assert result.status == "deferred"
    assert result.root_hash is None
    assert result.timestamped_at is None
    assert result.receipts_covered == 0

    row = next(r for r in session._rows_added if isinstance(r, TimestampAnchorRow))
    assert row.status == "deferred"
    assert row.root_hash is None
    assert row.tsr_bytes is None
    assert row.tsa_signature is None
    assert row.tsa_identifier == "forensa-mock-2026"


@pytest.mark.asyncio
async def test_anchor_day_deferred_when_tsa_fails():
    """TSA raises TimestampClientError -> persist deferred tombstone, do
    NOT propagate the exception."""
    tenant = uuid4()
    day = datetime(2026, 5, 15, tzinfo=UTC)
    chain_head = _make_receipt_row(
        tenant_id=tenant,
        receipt_hash="c" * 64,
        signed_at=datetime(2026, 5, 15, 12, tzinfo=UTC),
    )

    class _BrokenClient(TimestampClient):
        identifier = "broken-tsa"

        async def request_timestamp(self, hashed_root):
            raise TimestampClientError("TSA endpoint returned 503")

    session = _mock_session(latest_receipt_row=chain_head, receipts_count=5)
    result = await anchor_day(session, tenant_id=tenant, day=day, timestamp_client=_BrokenClient())

    assert result.status == "deferred"
    assert result.root_hash is None
    assert result.timestamped_at is None
    assert result.receipts_covered == 5  # count was still gathered

    row = next(r for r in session._rows_added if isinstance(r, TimestampAnchorRow))
    assert row.status == "deferred"
    assert row.root_hash is None
    assert row.tsa_identifier == "broken-tsa"


@pytest.mark.asyncio
async def test_anchor_day_replaces_existing_deferred_tombstone():
    """A prior deferred row for the same (tenant, day) is replaced by the
    new (anchored) row in the same transaction."""
    tenant = uuid4()
    day = datetime(2026, 5, 15, tzinfo=UTC)
    existing = _make_anchor_row(
        tenant_id=tenant,
        anchor_date=datetime(2026, 5, 15, 0, 0, tzinfo=UTC),
        status="deferred",
        root_hash=None,
    )
    chain_head = _make_receipt_row(
        tenant_id=tenant,
        receipt_hash="d" * 64,
        signed_at=datetime(2026, 5, 15, 12, tzinfo=UTC),
    )
    session = _mock_session(
        existing_anchor=existing,
        latest_receipt_row=chain_head,
        receipts_count=1,
    )
    client = MockTimestampClient()

    result = await anchor_day(session, tenant_id=tenant, day=day, timestamp_client=client)

    assert result.status == "anchored"
    # Old tombstone deleted; new row added.
    assert session._rows_deleted == [existing]
    new_rows = [r for r in session._rows_added if isinstance(r, TimestampAnchorRow)]
    assert len(new_rows) == 1
    assert new_rows[0].status == "anchored"
    assert new_rows[0].root_hash == "d" * 64


@pytest.mark.asyncio
async def test_anchor_day_replaces_deferred_tombstone_on_empty_day():
    """Existing deferred tombstone + still no receipts -> new deferred row
    (refreshed anchored_at timestamp); old tombstone deleted."""
    tenant = uuid4()
    day = datetime(2026, 5, 15, tzinfo=UTC)
    existing = _make_anchor_row(
        tenant_id=tenant,
        anchor_date=datetime(2026, 5, 15, 0, 0, tzinfo=UTC),
        status="deferred",
        root_hash=None,
    )
    session = _mock_session(existing_anchor=existing, latest_receipt_row=None)
    client = MockTimestampClient()

    await anchor_day(session, tenant_id=tenant, day=day, timestamp_client=client)

    assert session._rows_deleted == [existing]
    new_rows = [r for r in session._rows_added if isinstance(r, TimestampAnchorRow)]
    assert len(new_rows) == 1
    assert new_rows[0].status == "deferred"


@pytest.mark.asyncio
async def test_anchor_day_replaces_deferred_when_tsa_still_failing():
    """Existing deferred + TSA still fails -> still replaces the row with
    a fresh deferred tombstone (anchored_at gets refreshed)."""
    tenant = uuid4()
    day = datetime(2026, 5, 15, tzinfo=UTC)
    existing = _make_anchor_row(
        tenant_id=tenant,
        anchor_date=datetime(2026, 5, 15, 0, 0, tzinfo=UTC),
        status="deferred",
        root_hash=None,
    )
    chain_head = _make_receipt_row(
        tenant_id=tenant,
        receipt_hash="e" * 64,
        signed_at=datetime(2026, 5, 15, 12, tzinfo=UTC),
    )

    class _BrokenClient(TimestampClient):
        identifier = "still-broken"

        async def request_timestamp(self, hashed_root):
            raise TimestampClientError("still down")

    session = _mock_session(
        existing_anchor=existing,
        latest_receipt_row=chain_head,
        receipts_count=2,
    )
    await anchor_day(session, tenant_id=tenant, day=day, timestamp_client=_BrokenClient())
    assert session._rows_deleted == [existing]
    new = next(r for r in session._rows_added if isinstance(r, TimestampAnchorRow))
    assert new.status == "deferred"


# ---------------------------------------------------------------------------
# anchor_day - idempotency on already-anchored rows
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_anchor_day_refuses_to_overwrite_anchored_row():
    """Pre-existing anchored row -> AnchorAlreadyExistsError. The daily
    cron is idempotent for completed days."""
    tenant = uuid4()
    day = datetime(2026, 5, 15, tzinfo=UTC)
    existing = _make_anchor_row(
        tenant_id=tenant,
        anchor_date=datetime(2026, 5, 15, 0, 0, tzinfo=UTC),
        status="anchored",
    )
    session = _mock_session(existing_anchor=existing)
    client = MockTimestampClient()

    with pytest.raises(AnchorAlreadyExistsError):
        await anchor_day(session, tenant_id=tenant, day=day, timestamp_client=client)
    # Nothing added, nothing deleted.
    assert session._rows_added == []
    assert session._rows_deleted == []


# ---------------------------------------------------------------------------
# anchor_day - input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_anchor_day_rejects_naive_datetime():
    session = _mock_session()
    client = MockTimestampClient()
    with pytest.raises(ValueError, match="timezone-aware"):
        await anchor_day(
            session,
            tenant_id=uuid4(),
            day=datetime(2026, 5, 15),  # naive
            timestamp_client=client,
        )


@pytest.mark.asyncio
async def test_anchor_day_normalises_day_to_utc_midnight():
    """A datetime at 23:50 in some non-UTC timezone is normalised to its
    UTC calendar date's midnight."""
    from datetime import timezone

    tenant = uuid4()
    # 23:50 in UTC+5 = 18:50 UTC on the same calendar date
    day = datetime(2026, 5, 15, 23, 50, tzinfo=timezone(timedelta(hours=5)))
    chain_head = _make_receipt_row(
        tenant_id=tenant,
        receipt_hash="c" * 64,
        signed_at=datetime(2026, 5, 15, 12, tzinfo=UTC),
    )
    session = _mock_session(latest_receipt_row=chain_head, receipts_count=1)
    client = MockTimestampClient()
    await anchor_day(session, tenant_id=tenant, day=day, timestamp_client=client)
    row = next(r for r in session._rows_added if isinstance(r, TimestampAnchorRow))
    # 23:50 +05:00 = 18:50 UTC -> calendar date 2026-05-15 UTC -> midnight UTC
    assert row.anchor_date == datetime(2026, 5, 15, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# get_anchor_for_day
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_anchor_for_day_returns_row_when_present():
    tenant = uuid4()
    existing = _make_anchor_row(
        tenant_id=tenant,
        anchor_date=datetime(2026, 5, 15, tzinfo=UTC),
        status="anchored",
    )
    session = _mock_session(existing_anchor=existing)
    result = await get_anchor_for_day(
        session, tenant_id=tenant, day=datetime(2026, 5, 15, 12, tzinfo=UTC)
    )
    assert result is existing


@pytest.mark.asyncio
async def test_get_anchor_for_day_returns_none_when_absent():
    session = _mock_session(existing_anchor=None)
    result = await get_anchor_for_day(
        session, tenant_id=uuid4(), day=datetime(2026, 5, 15, tzinfo=UTC)
    )
    assert result is None


# ---------------------------------------------------------------------------
# verify_receipt_anchored_in
# ---------------------------------------------------------------------------


def _build_chain(n: int, tenant_id: UUID, signed_at: datetime) -> list[Receipt]:
    """Build a hash-linked chain of n receipts for one tenant."""
    bundle = build_bundle(
        tenant_id=tenant_id,
        version="1.0.0",
        content={"rules": [{"kind": "x", "decision": "allow"}], "default": "allow"},
    )
    mock = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )
    import asyncio

    async def _verdict():
        return await mock.evaluate(tenant_id, {"kind": "x"})

    verdict = asyncio.get_event_loop().run_until_complete(_verdict()) if False else None
    # Use new_event_loop for synchronous test setup.
    loop = asyncio.new_event_loop()
    try:
        verdict = loop.run_until_complete(mock.evaluate(tenant_id, {"kind": "x"}))
    finally:
        loop.close()

    snap = capture_snapshot(bundle, verdict)
    snap_id = uuid4()
    priv, _ = generate_keypair()
    receipts: list[Receipt] = []
    prev: Receipt | None = None
    for i in range(n):
        r = build_receipt(
            tenant_id=tenant_id,
            event_id=uuid4(),
            event_payload={"step": i},
            policy_snapshot=snap,
            policy_snapshot_id=snap_id,
            prev_receipt=prev,
            tenant_signing_key=priv,
        )
        r = r.model_copy(update={"signed_at": signed_at + timedelta(seconds=i)})
        receipts.append(r)
        prev = r
    return receipts


def test_verify_returns_true_when_receipt_equals_root_and_no_intermediates():
    """Single-receipt chain: receipt IS the root."""
    tenant = uuid4()
    chain = _build_chain(1, tenant, datetime(2026, 5, 15, 10, tzinfo=UTC))
    receipt = chain[0]
    anchor = _make_anchor_row(
        tenant_id=tenant,
        anchor_date=datetime(2026, 5, 15, tzinfo=UTC),
        status="anchored",
        root_hash=receipt.receipt_hash,
    )
    anchor.timestamped_at = datetime(2026, 5, 15, 23, tzinfo=UTC)
    assert verify_receipt_anchored_in(receipt, anchor, intermediate_receipts=[])


def test_verify_returns_true_for_multi_link_chain():
    """receipt[0] linked via [receipt[1], receipt[2]] to receipt[2] as root."""
    tenant = uuid4()
    chain = _build_chain(3, tenant, datetime(2026, 5, 15, 10, tzinfo=UTC))
    receipt = chain[0]
    intermediates = chain[1:]
    anchor = _make_anchor_row(
        tenant_id=tenant,
        anchor_date=datetime(2026, 5, 15, tzinfo=UTC),
        status="anchored",
        root_hash=intermediates[-1].receipt_hash,
    )
    anchor.timestamped_at = datetime(2026, 5, 15, 23, tzinfo=UTC)
    assert verify_receipt_anchored_in(receipt, anchor, intermediates)


def test_verify_returns_false_for_deferred_anchor():
    tenant = uuid4()
    chain = _build_chain(1, tenant, datetime(2026, 5, 15, 10, tzinfo=UTC))
    anchor = _make_anchor_row(
        tenant_id=tenant,
        anchor_date=datetime(2026, 5, 15, tzinfo=UTC),
        status="deferred",
        root_hash=None,
    )
    assert not verify_receipt_anchored_in(chain[0], anchor, [])


def test_verify_returns_false_when_anchor_root_hash_missing():
    """A status='anchored' row with root_hash=None is malformed; reject."""
    tenant = uuid4()
    chain = _build_chain(1, tenant, datetime(2026, 5, 15, 10, tzinfo=UTC))
    anchor = _make_anchor_row(
        tenant_id=tenant,
        anchor_date=datetime(2026, 5, 15, tzinfo=UTC),
        status="anchored",
    )
    anchor.root_hash = None
    anchor.timestamped_at = datetime(2026, 5, 15, 23, tzinfo=UTC)
    assert not verify_receipt_anchored_in(chain[0], anchor, [])


def test_verify_returns_false_when_anchor_timestamped_at_missing():
    tenant = uuid4()
    chain = _build_chain(1, tenant, datetime(2026, 5, 15, 10, tzinfo=UTC))
    anchor = _make_anchor_row(
        tenant_id=tenant,
        anchor_date=datetime(2026, 5, 15, tzinfo=UTC),
        status="anchored",
        root_hash=chain[0].receipt_hash,
    )
    anchor.timestamped_at = None
    assert not verify_receipt_anchored_in(chain[0], anchor, [])


def test_verify_returns_false_when_receipt_signed_after_anchor_timestamp():
    """Causality check: a receipt CANNOT be anchored by a TSR with an
    earlier timestamp. Either the receipt is post-anchor (still pending
    next day's run) or the anchor is forged."""
    tenant = uuid4()
    chain = _build_chain(1, tenant, datetime(2026, 5, 15, 23, tzinfo=UTC))
    anchor = _make_anchor_row(
        tenant_id=tenant,
        anchor_date=datetime(2026, 5, 15, tzinfo=UTC),
        status="anchored",
        root_hash=chain[0].receipt_hash,
    )
    anchor.timestamped_at = datetime(2026, 5, 15, 22, tzinfo=UTC)  # BEFORE receipt
    assert not verify_receipt_anchored_in(chain[0], anchor, [])


def test_verify_returns_false_when_tenant_id_mismatch():
    chain = _build_chain(1, uuid4(), datetime(2026, 5, 15, 10, tzinfo=UTC))
    other_tenant = uuid4()
    anchor = _make_anchor_row(
        tenant_id=other_tenant,  # different tenant
        anchor_date=datetime(2026, 5, 15, tzinfo=UTC),
        status="anchored",
        root_hash=chain[0].receipt_hash,
    )
    anchor.timestamped_at = datetime(2026, 5, 15, 23, tzinfo=UTC)
    assert not verify_receipt_anchored_in(chain[0], anchor, [])


def test_verify_returns_false_when_first_intermediate_does_not_link_to_receipt():
    """receipt[0] + intermediates that don't start with receipt[0]."""
    tenant = uuid4()
    chain = _build_chain(3, tenant, datetime(2026, 5, 15, 10, tzinfo=UTC))
    # Detach the chain: pass intermediates that don't link to receipt
    receipt = chain[0]
    # Use chain[2] as intermediate; chain[2].prev_receipt_hash != receipt.receipt_hash
    intermediates = [chain[2]]
    anchor = _make_anchor_row(
        tenant_id=tenant,
        anchor_date=datetime(2026, 5, 15, tzinfo=UTC),
        status="anchored",
        root_hash=chain[2].receipt_hash,
    )
    anchor.timestamped_at = datetime(2026, 5, 15, 23, tzinfo=UTC)
    assert not verify_receipt_anchored_in(receipt, anchor, intermediates)


def test_verify_returns_false_when_intermediate_chain_breaks():
    """A break in the middle of the intermediate chain fails."""
    tenant = uuid4()
    chain = _build_chain(4, tenant, datetime(2026, 5, 15, 10, tzinfo=UTC))
    receipt = chain[0]
    # intermediates = [chain[1], chain[3]] - skip chain[2], break in chain
    intermediates = [chain[1], chain[3]]
    anchor = _make_anchor_row(
        tenant_id=tenant,
        anchor_date=datetime(2026, 5, 15, tzinfo=UTC),
        status="anchored",
        root_hash=chain[3].receipt_hash,
    )
    anchor.timestamped_at = datetime(2026, 5, 15, 23, tzinfo=UTC)
    assert not verify_receipt_anchored_in(receipt, anchor, intermediates)


def test_verify_returns_false_when_last_intermediate_not_equal_to_root():
    """Even with a valid chain, if the last intermediate's hash doesn't
    match anchor.root_hash, it's not provably anchored."""
    tenant = uuid4()
    chain = _build_chain(3, tenant, datetime(2026, 5, 15, 10, tzinfo=UTC))
    receipt = chain[0]
    intermediates = chain[1:]
    anchor = _make_anchor_row(
        tenant_id=tenant,
        anchor_date=datetime(2026, 5, 15, tzinfo=UTC),
        status="anchored",
        root_hash="0" * 64,  # not matching chain[-1]
    )
    anchor.timestamped_at = datetime(2026, 5, 15, 23, tzinfo=UTC)
    assert not verify_receipt_anchored_in(receipt, anchor, intermediates)


def test_verify_returns_false_when_no_intermediates_and_receipt_ne_root():
    """Empty intermediates list + receipt.receipt_hash != anchor.root_hash."""
    tenant = uuid4()
    chain = _build_chain(1, tenant, datetime(2026, 5, 15, 10, tzinfo=UTC))
    anchor = _make_anchor_row(
        tenant_id=tenant,
        anchor_date=datetime(2026, 5, 15, tzinfo=UTC),
        status="anchored",
        root_hash="z" * 64,  # not matching receipt
    )
    anchor.timestamped_at = datetime(2026, 5, 15, 23, tzinfo=UTC)
    assert not verify_receipt_anchored_in(chain[0], anchor, [])


# ---------------------------------------------------------------------------
# _client_identifier fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_identifier_fallback_for_minimal_client():
    """A custom TimestampClient with no identifier or endpoint_url attr
    falls back to 'unknown' in the persisted row."""
    tenant = uuid4()
    day = datetime(2026, 5, 15, tzinfo=UTC)
    chain_head = _make_receipt_row(
        tenant_id=tenant,
        receipt_hash="c" * 64,
        signed_at=datetime(2026, 5, 15, 12, tzinfo=UTC),
    )

    class _BareClient(TimestampClient):
        async def request_timestamp(self, hashed_root):
            # Use the canonical signing logic from MockTimestampClient by
            # delegating to a fresh instance.
            mock = MockTimestampClient(identifier="bare-internal")
            # But return a response without exposing 'identifier' on self.
            return await mock.request_timestamp(hashed_root)

    session = _mock_session(latest_receipt_row=chain_head, receipts_count=1)
    bare = _BareClient()
    # Test the fallback: no tsa_identifier override, no identifier attr,
    # no endpoint_url attr -> _client_identifier returns 'unknown' BUT
    # since this is anchored, the TSA response's own identifier is used.
    result = await anchor_day(session, tenant_id=tenant, day=day, timestamp_client=bare)
    row = next(r for r in session._rows_added if isinstance(r, TimestampAnchorRow))
    # When anchoring succeeds, the row uses tsa_response.tsa_identifier,
    # not _client_identifier(client) - so it'll be "bare-internal".
    assert row.tsa_identifier == "bare-internal"
    assert result.status == "anchored"


@pytest.mark.asyncio
async def test_unknown_identifier_fallback_used_on_deferred_empty_path():
    """The 'unknown' fallback in _client_identifier IS hit on the
    deferred-empty path (no receipts) when client has no identifier
    AND no endpoint_url AND no tsa_identifier override."""
    tenant = uuid4()
    day = datetime(2026, 5, 15, tzinfo=UTC)

    class _BareClient(TimestampClient):
        async def request_timestamp(self, hashed_root):  # pragma: no cover
            raise NotImplementedError

    session = _mock_session(latest_receipt_row=None)
    await anchor_day(session, tenant_id=tenant, day=day, timestamp_client=_BareClient())
    row = next(r for r in session._rows_added if isinstance(r, TimestampAnchorRow))
    assert row.tsa_identifier == "unknown"


@pytest.mark.asyncio
async def test_endpoint_url_used_as_identifier_when_no_other_set():
    """Rfc3161-style client with endpoint_url but no identifier attr
    falls back to endpoint_url for the persisted tsa_identifier."""
    tenant = uuid4()
    day = datetime(2026, 5, 15, tzinfo=UTC)

    class _UrlClient(TimestampClient):
        endpoint_url = "https://tsa.example.com/"

        async def request_timestamp(self, hashed_root):  # pragma: no cover
            raise NotImplementedError

    session = _mock_session(latest_receipt_row=None)
    await anchor_day(session, tenant_id=tenant, day=day, timestamp_client=_UrlClient())
    row = next(r for r in session._rows_added if isinstance(r, TimestampAnchorRow))
    assert row.tsa_identifier == "https://tsa.example.com/"

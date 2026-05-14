"""Unit tests for ``apps.api.idempotency_store`` (CP9.17 / NEW-P9.8.2).

Covers:
- ``is_valid_idempotency_key`` regex contract.
- ``compute_body_hash`` determinism + key-order invariance.
- ``InMemoryIdempotencyStore`` lookup / claim / store / conflict / TTL paths.
- ``IdempotencyKeyConflict`` truncation in the error message.
- ``StoredIdempotencyRecord`` immutability.
- ``PostgresIdempotencyStore`` shape via mocked AsyncSession - the SQL
  payload is asserted but no real DB is hit at this layer. Real PG
  verification rides on the migration round-trip test in
  tests/integration/test_pg_migrations.py.
"""

from __future__ import annotations

import asyncio
import dataclasses
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from apps.api.idempotency_store import (
    IdempotencyKeyConflict,
    InMemoryIdempotencyStore,
    PostgresIdempotencyStore,
    StoredIdempotencyRecord,
    compute_body_hash,
    is_valid_idempotency_key,
)

# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestIsValidIdempotencyKey:
    @pytest.mark.parametrize(
        "good",
        [
            "a" * 16,
            "a" * 128,
            "A1z9-_aaaaaaaaaa",
            "key_with-underscores-and-dashes-and-numbers-1234567890",
            "X" * 17,
            "x" * 127,
        ],
    )
    def test_accepts_valid(self, good: str) -> None:
        assert is_valid_idempotency_key(good)

    @pytest.mark.parametrize(
        "bad",
        [
            "",
            "a" * 15,
            "a" * 129,
            "has space here1234",
            "has/slash/aaaaaaa",
            "has.dot.aaaaaaaaa",
            "has;semi;aaaaaaaa",
            "has@at@aaaaaaaaaaa",
            "has\nnewline\naaaaa",
        ],
    )
    def test_rejects_invalid(self, bad: str) -> None:
        assert not is_valid_idempotency_key(bad)


class TestComputeBodyHash:
    def test_returns_64_char_hex(self) -> None:
        h = compute_body_hash({"a": 1})
        assert len(h) == 64
        int(h, 16)  # raises if not hex

    def test_key_order_invariant(self) -> None:
        """Canonical JSON sorts keys; two dicts with same content + different
        insertion order produce the same hash."""
        a = compute_body_hash({"x": 1, "y": 2, "z": 3})
        b = compute_body_hash({"z": 3, "y": 2, "x": 1})
        assert a == b

    def test_value_difference_changes_hash(self) -> None:
        assert compute_body_hash({"x": 1}) != compute_body_hash({"x": 2})

    def test_nested_structures_normalised(self) -> None:
        a = compute_body_hash({"outer": {"a": 1, "b": 2}})
        b = compute_body_hash({"outer": {"b": 2, "a": 1}})
        assert a == b


# ---------------------------------------------------------------------------
# StoredIdempotencyRecord
# ---------------------------------------------------------------------------


class TestStoredIdempotencyRecord:
    def test_frozen(self) -> None:
        now = datetime.now(UTC)
        record = StoredIdempotencyRecord(
            tenant_id=uuid4(),
            key="k" * 16,
            body_hash="a" * 64,
            response_status=201,
            response_body={"x": 1},
            stored_at=now,
            expires_at=now + timedelta(hours=24),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            record.body_hash = "b" * 64  # type: ignore[misc]


# ---------------------------------------------------------------------------
# IdempotencyKeyConflict
# ---------------------------------------------------------------------------


class TestIdempotencyKeyConflict:
    def test_message_truncates_hashes(self) -> None:
        exc = IdempotencyKeyConflict(
            key="key" + "x" * 13,
            expected_body_hash="a" * 64,
            actual_body_hash="b" * 64,
        )
        msg = str(exc)
        # Truncation: first 12 chars of each hash appear, full 64 doesn't.
        assert "aaaaaaaaaaaa" in msg
        assert "bbbbbbbbbbbb" in msg
        assert "a" * 64 not in msg
        assert "b" * 64 not in msg

    def test_fields_exposed_on_exception(self) -> None:
        exc = IdempotencyKeyConflict(
            key="some-test-key-1234",
            expected_body_hash="a" * 64,
            actual_body_hash="b" * 64,
        )
        assert exc.key == "some-test-key-1234"
        assert exc.expected_body_hash == "a" * 64
        assert exc.actual_body_hash == "b" * 64


# ---------------------------------------------------------------------------
# InMemoryIdempotencyStore
# ---------------------------------------------------------------------------


class TestInMemoryIdempotencyStore:
    @pytest.mark.asyncio
    async def test_first_lookup_returns_none(self) -> None:
        store = InMemoryIdempotencyStore()
        result = await store.lookup_or_claim(uuid4(), "k" * 16, "h" * 64)
        assert result is None

    @pytest.mark.asyncio
    async def test_store_then_lookup_returns_record(self) -> None:
        store = InMemoryIdempotencyStore()
        tenant = uuid4()
        key = "k" * 16
        bh = "h" * 64
        await store.store(tenant, key, bh, 201, {"hello": "world"})
        record = await store.lookup_or_claim(tenant, key, bh)
        assert record is not None
        assert record.response_body == {"hello": "world"}
        assert record.response_status == 201

    @pytest.mark.asyncio
    async def test_same_key_different_body_raises_conflict(self) -> None:
        store = InMemoryIdempotencyStore()
        tenant = uuid4()
        key = "k" * 16
        await store.store(tenant, key, "a" * 64, 201, {"v": 1})
        with pytest.raises(IdempotencyKeyConflict):
            await store.lookup_or_claim(tenant, key, "b" * 64)

    @pytest.mark.asyncio
    async def test_different_tenants_isolated(self) -> None:
        store = InMemoryIdempotencyStore()
        tenant_a = uuid4()
        tenant_b = uuid4()
        key = "k" * 16
        bh = "h" * 64
        await store.store(tenant_a, key, bh, 201, {"who": "a"})
        # Tenant B lookup with same key returns None (independent slot).
        assert await store.lookup_or_claim(tenant_b, key, bh) is None

    @pytest.mark.asyncio
    async def test_expired_record_returns_none_and_is_purged(self) -> None:
        store = InMemoryIdempotencyStore(default_ttl=timedelta(seconds=0))
        tenant = uuid4()
        key = "k" * 16
        bh = "h" * 64
        await store.store(tenant, key, bh, 201, {"x": 1})
        # Born-expired; first lookup purges the tombstone.
        result = await store.lookup_or_claim(tenant, key, bh)
        assert result is None
        # And the internal dict no longer has the record.
        assert (tenant, key) not in store._records

    @pytest.mark.asyncio
    async def test_second_store_is_no_op(self) -> None:
        """``store`` is idempotent itself: a second call for the same key
        does NOT overwrite the original record."""
        store = InMemoryIdempotencyStore()
        tenant = uuid4()
        key = "k" * 16
        bh = "h" * 64
        await store.store(tenant, key, bh, 201, {"version": 1})
        await store.store(tenant, key, bh, 201, {"version": 2})
        record = await store.lookup_or_claim(tenant, key, bh)
        assert record is not None
        assert record.response_body == {"version": 1}

    @pytest.mark.asyncio
    async def test_explicit_ttl_overrides_default(self) -> None:
        """When ``store`` is called with an explicit ttl arg, that value is
        used in preference to the constructor default."""
        store = InMemoryIdempotencyStore(default_ttl=timedelta(hours=24))
        tenant = uuid4()
        key = "k" * 16
        bh = "h" * 64
        # Born-expired explicit TTL even though default is 24h.
        await store.store(tenant, key, bh, 201, {"x": 1}, ttl=timedelta(seconds=0))
        result = await store.lookup_or_claim(tenant, key, bh)
        assert result is None

    @pytest.mark.asyncio
    async def test_concurrent_lookups_serialised(self) -> None:
        """Two concurrent lookup_or_claim calls for the same empty slot:
        both return None (lock guarantees they don't see partial state)."""
        store = InMemoryIdempotencyStore()
        tenant = uuid4()
        key = "k" * 16
        bh = "h" * 64
        r1, r2 = await asyncio.gather(
            store.lookup_or_claim(tenant, key, bh),
            store.lookup_or_claim(tenant, key, bh),
        )
        assert r1 is None
        assert r2 is None


# ---------------------------------------------------------------------------
# PostgresIdempotencyStore (mocked session)
# ---------------------------------------------------------------------------


class TestPostgresIdempotencyStore:
    """Shape-only tests: the SQL is executed against a mocked AsyncSession.
    Real PG verification is covered by the alembic migration test in
    tests/integration/test_pg_migrations.py (verifies the table exists +
    survives round-trip) plus the end-to-end happy-path test in
    test_events_idempotency.py (verifies the lookup/store contract).
    """

    def _mock_session_with_row(self, row_tuple):
        result = MagicMock()
        result.first = MagicMock(return_value=row_tuple)
        session = MagicMock()
        session.execute = AsyncMock(return_value=result)
        return session

    @pytest.mark.asyncio
    async def test_lookup_returns_none_when_no_row(self) -> None:
        session = self._mock_session_with_row(None)
        store = PostgresIdempotencyStore(session)
        result = await store.lookup_or_claim(uuid4(), "k" * 16, "h" * 64)
        assert result is None

    @pytest.mark.asyncio
    async def test_lookup_returns_record_when_row_found(self) -> None:
        tenant = uuid4()
        now = datetime.now(UTC)
        row = (
            tenant,
            "k" * 16,
            "h" * 64,
            201,
            {"hello": "world"},
            now,
            now + timedelta(hours=24),
        )
        session = self._mock_session_with_row(row)
        store = PostgresIdempotencyStore(session)
        record = await store.lookup_or_claim(tenant, "k" * 16, "h" * 64)
        assert record is not None
        assert record.tenant_id == tenant
        assert record.response_body == {"hello": "world"}

    @pytest.mark.asyncio
    async def test_lookup_raises_conflict_on_body_hash_mismatch(self) -> None:
        tenant = uuid4()
        now = datetime.now(UTC)
        row = (
            tenant,
            "k" * 16,
            "a" * 64,
            201,
            {},
            now,
            now + timedelta(hours=24),
        )
        session = self._mock_session_with_row(row)
        store = PostgresIdempotencyStore(session)
        with pytest.raises(IdempotencyKeyConflict):
            await store.lookup_or_claim(tenant, "k" * 16, "b" * 64)

    @pytest.mark.asyncio
    async def test_store_issues_insert_on_conflict_do_nothing(self) -> None:
        session = MagicMock()
        session.execute = AsyncMock()
        store = PostgresIdempotencyStore(session)
        await store.store(
            tenant_id=uuid4(),
            key="k" * 16,
            body_hash="h" * 64,
            response_status=201,
            response_body={"x": 1},
        )
        # Exactly one SQL call was issued.
        assert session.execute.await_count == 1
        # The SQL text contains the ON CONFLICT clause that makes the
        # insert idempotent under concurrent calls.
        call_args = session.execute.await_args
        sql_clause = str(call_args.args[0])
        assert "ON CONFLICT" in sql_clause
        assert "DO NOTHING" in sql_clause

    @pytest.mark.asyncio
    async def test_store_passes_explicit_ttl_through(self) -> None:
        session = MagicMock()
        session.execute = AsyncMock()
        store = PostgresIdempotencyStore(session, default_ttl=timedelta(hours=24))
        await store.store(
            tenant_id=uuid4(),
            key="k" * 16,
            body_hash="h" * 64,
            response_status=201,
            response_body={},
            ttl=timedelta(seconds=60),
        )
        params = session.execute.await_args.args[1]
        delta = params["expires"] - params["stored"]
        assert delta == timedelta(seconds=60)

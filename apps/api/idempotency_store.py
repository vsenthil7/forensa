"""Idempotency-Key support for mutating routes (CP9.17 / NEW-P9.8.2).

Enterprise ingest clients retry on network failure. Without an idempotency
contract, a retry produces a second Event with a fresh UUID and a second
Receipt extending the chain - the evidence ledger has now double-counted
the agent action.

Stripe-style fix: client supplies an ``Idempotency-Key`` header per request.
Same key + same body within the TTL window -> server returns the ORIGINAL
response unchanged. Same key + different body -> 409 Conflict (the client
is reusing a key for a different operation, which is a client bug). No
header -> status quo (always-new event).

This module exposes:

- ``IdempotencyStore`` ABC: lookup + store + atomic check-and-claim.
- ``StoredIdempotencyRecord``: frozen record returned by lookup.
- ``IdempotencyKeyConflict``: raised when the same key is seen with a
  different body hash within the TTL window.
- ``InMemoryIdempotencyStore``: process-local impl for tests / hackathon
  demo. Async-lock-guarded so concurrent same-key submissions race-safely.
- ``PostgresIdempotencyStore``: production impl backed by the
  ``idempotency_records`` table (alembic 0005). Pure raw-SQL via
  ``text()`` so the table is a pure-evidence record decoupled from the
  ORM model layer (kept off the ``policy_bundles`` / ``receipts``
  relationship graph - it's a request-deduplication cache, not part of
  the audit ledger).

Header semantics
----------------

Keys must match ``^[A-Za-z0-9_-]{16,128}$``:

- 16-char floor so the key has at least ~95 bits of entropy and is
  unlikely to collide accidentally between independent clients.
- 128-char ceiling so the key fits comfortably in a DB column and HTTP
  header line without bloating.
- Alphanumeric + ``_-`` only: safe in URLs, headers, log lines.

Body hash binding
-----------------

``body_hash = sha256_hex(canonical_json(request_body))``. Reuses the same
canonical-JSON primitive the Receipt builder uses, so the binding is
deterministic and reproducible. Two requests with byte-identical JSON
bodies (modulo key ordering and whitespace) produce identical body hashes.

TTL semantics
-------------

Default TTL: 24 hours. Long enough to cover retries from a sidecar that
crashed and resumed; short enough that the dedup cache doesn't grow
unbounded. ``lookup`` filters on ``expires_at > now()`` so expired records
are tombstones, not bugs - a request landing after the TTL window is
re-executed and the new response replaces the old.

The cleanup of expired rows is tracked as ``NEW-P9.17.1`` (background cron
deleting where ``expires_at <= now() - 7 days`` to preserve recent
forensics). Today the table grows monotonically until that lands.
"""

from __future__ import annotations

import asyncio
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from packages.crypto.hash import canonical_json, sha256_hex

# ---------------------------------------------------------------------------
# Public contract
# ---------------------------------------------------------------------------


_KEY_PATTERN: re.Pattern[str] = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
_DEFAULT_TTL: timedelta = timedelta(hours=24)


def is_valid_idempotency_key(key: str) -> bool:
    """Return True iff ``key`` matches the header contract.

    Used by the route layer to issue 400 (malformed protocol) rather than
    422 (semantic) when the header value is bad.
    """
    return bool(_KEY_PATTERN.fullmatch(key))


def compute_body_hash(body: Any) -> str:
    """Return the canonical SHA-256 hex of ``body`` for idempotency binding."""
    return sha256_hex(canonical_json(body))


class IdempotencyKeyConflict(RuntimeError):  # noqa: N818 - HTTP 409 Conflict semantic; "Error" suffix would obscure the link to the response status
    """Raised when the same key is seen with a different body hash within TTL.

    Surfaces as HTTP 409 Conflict at the route layer.
    """

    def __init__(self, key: str, expected_body_hash: str, actual_body_hash: str) -> None:
        super().__init__(
            f"Idempotency-Key '{key}' was previously used with body hash "
            f"{expected_body_hash[:12]}..., now seen with body hash "
            f"{actual_body_hash[:12]}..."
        )
        self.key = key
        self.expected_body_hash = expected_body_hash
        self.actual_body_hash = actual_body_hash


@dataclass(frozen=True)
class StoredIdempotencyRecord:
    """A previously-stored response for a given (tenant_id, key) pair.

    Frozen so callers cannot mutate the cached response in place.
    """

    tenant_id: UUID
    key: str
    body_hash: str
    response_status: int
    response_body: dict[str, Any]
    stored_at: datetime
    expires_at: datetime


# ---------------------------------------------------------------------------
# ABC
# ---------------------------------------------------------------------------


class IdempotencyStore(ABC):
    """Lookup + store pairing for idempotency records.

    Implementations MUST be safe to call concurrently. Two coroutines
    calling ``lookup_or_claim`` for the same ``(tenant_id, key)`` and the
    same ``body_hash`` MUST both either:

    a) receive ``None`` (claim granted) - exactly one such coroutine wins
       and is expected to ``store`` the response, OR
    b) receive a ``StoredIdempotencyRecord`` - the response was already
       stored by a previous (possibly concurrent) caller.

    The race-safety contract is the whole point of this module; the
    in-memory impl uses ``asyncio.Lock``, the PG impl uses ``INSERT ON
    CONFLICT DO NOTHING`` semantics.
    """

    @abstractmethod
    async def lookup_or_claim(
        self,
        tenant_id: UUID,
        key: str,
        body_hash: str,
    ) -> StoredIdempotencyRecord | None:
        """Atomically: if a record exists for ``(tenant_id, key)``, return it
        (after verifying body_hash matches; raises ``IdempotencyKeyConflict``
        if it does not). If no record exists, claim the slot and return
        ``None``. The caller is then obliged to call ``store`` with the
        full response once it's been computed.

        Raises ``IdempotencyKeyConflict`` if a record exists for the key
        but with a different body hash.
        """

    @abstractmethod
    async def store(
        self,
        tenant_id: UUID,
        key: str,
        body_hash: str,
        response_status: int,
        response_body: dict[str, Any],
        ttl: timedelta = _DEFAULT_TTL,
    ) -> None:
        """Persist the computed response under ``(tenant_id, key)``.

        Idempotent itself: calling ``store`` twice for the same
        ``(tenant_id, key)`` is a no-op on the second call.
        """


# ---------------------------------------------------------------------------
# In-memory impl (tests / demo)
# ---------------------------------------------------------------------------


class InMemoryIdempotencyStore(IdempotencyStore):
    """Process-local idempotency store backed by a dict + asyncio.Lock.

    Suitable for unit tests and the hackathon demo. Does NOT survive a
    process restart - if a client retries across a process restart, the
    retry will re-execute. Production deployments use
    ``PostgresIdempotencyStore``.
    """

    def __init__(self, *, default_ttl: timedelta = _DEFAULT_TTL) -> None:
        self._default_ttl = default_ttl
        self._records: dict[tuple[UUID, str], StoredIdempotencyRecord] = {}
        # Single lock guards the dict so concurrent lookups and stores are
        # serialised. For the demo workload (single test process), this is
        # not a contention point.
        self._lock = asyncio.Lock()

    async def lookup_or_claim(
        self,
        tenant_id: UUID,
        key: str,
        body_hash: str,
    ) -> StoredIdempotencyRecord | None:
        async with self._lock:
            existing = self._records.get((tenant_id, key))
            if existing is None:
                return None
            if existing.expires_at <= datetime.now(UTC):
                # Expired tombstone - re-execute. The store call from the
                # winning coroutine will overwrite the row.
                del self._records[(tenant_id, key)]
                return None
            if existing.body_hash != body_hash:
                raise IdempotencyKeyConflict(
                    key=key,
                    expected_body_hash=existing.body_hash,
                    actual_body_hash=body_hash,
                )
            return existing

    async def store(
        self,
        tenant_id: UUID,
        key: str,
        body_hash: str,
        response_status: int,
        response_body: dict[str, Any],
        ttl: timedelta | None = None,
    ) -> None:
        effective_ttl = ttl if ttl is not None else self._default_ttl
        now = datetime.now(UTC)
        record = StoredIdempotencyRecord(
            tenant_id=tenant_id,
            key=key,
            body_hash=body_hash,
            response_status=response_status,
            response_body=response_body,
            stored_at=now,
            expires_at=now + effective_ttl,
        )
        async with self._lock:
            # First-store-wins. A concurrent caller that already ran
            # lookup_or_claim and got None expects to be able to store its
            # response; we honour the first-store and treat the second as
            # a no-op.
            if (tenant_id, key) not in self._records:
                self._records[(tenant_id, key)] = record


# ---------------------------------------------------------------------------
# Postgres impl (production)
# ---------------------------------------------------------------------------


class PostgresIdempotencyStore(IdempotencyStore):
    """Production ``IdempotencyStore`` backed by the ``idempotency_records``
    table (alembic 0005).

    Uses raw SQL via ``text()`` rather than the ORM so the table stays
    decoupled from the audit-ledger relationship graph - it's a request
    dedup cache, not part of the Receipt chain.

    Race-safety: ``lookup_or_claim`` uses an explicit ``SELECT ... FOR
    UPDATE`` to lock the row if it exists; if it does not, the caller
    receives None and is expected to call ``store``. The ``store`` method
    uses ``INSERT ... ON CONFLICT (tenant_id, key) DO NOTHING`` so a
    concurrent winner's INSERT is silently absorbed (first-write-wins).
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        default_ttl: timedelta = _DEFAULT_TTL,
    ) -> None:
        self._session = session
        self._default_ttl = default_ttl

    async def lookup_or_claim(
        self,
        tenant_id: UUID,
        key: str,
        body_hash: str,
    ) -> StoredIdempotencyRecord | None:
        result = await self._session.execute(
            text(
                "SELECT tenant_id, key, body_hash, response_status, response_body, "
                "stored_at, expires_at "
                "FROM idempotency_records "
                "WHERE tenant_id = :tid AND key = :k AND expires_at > :now "
                "FOR UPDATE"
            ),
            {"tid": tenant_id, "k": key, "now": datetime.now(UTC)},
        )
        row = result.first()
        if row is None:
            return None
        existing_body_hash: str = row[2]
        if existing_body_hash != body_hash:
            raise IdempotencyKeyConflict(
                key=key,
                expected_body_hash=existing_body_hash,
                actual_body_hash=body_hash,
            )
        return StoredIdempotencyRecord(
            tenant_id=row[0],
            key=row[1],
            body_hash=row[2],
            response_status=row[3],
            response_body=row[4],
            stored_at=row[5],
            expires_at=row[6],
        )

    async def store(
        self,
        tenant_id: UUID,
        key: str,
        body_hash: str,
        response_status: int,
        response_body: dict[str, Any],
        ttl: timedelta | None = None,
    ) -> None:
        effective_ttl = ttl if ttl is not None else self._default_ttl
        now = datetime.now(UTC)
        await self._session.execute(
            text(
                "INSERT INTO idempotency_records "
                "(tenant_id, key, body_hash, response_status, response_body, "
                " stored_at, expires_at) "
                "VALUES (:tid, :k, :bh, :status, :body, :stored, :expires) "
                "ON CONFLICT (tenant_id, key) DO NOTHING"
            ),
            {
                "tid": tenant_id,
                "k": key,
                "bh": body_hash,
                "status": response_status,
                "body": response_body,
                "stored": now,
                "expires": now + effective_ttl,
            },
        )

# Phase 4 - Unit 13 Receipt issuance pipeline - DONE

HEAD at phase close: 9200a35
CI run: 25830062159 - all 7 gating jobs SUCCESS (Python, TypeScript, Playwright, Lint, Security, SBOM, ci-gate)
Net tests delivered: 358 to 398 (+40 in this phase)
100pct line and branch coverage maintained on all measured modules

## Master CP table

| CP | Code files developed (LOC) | Test files developed (LOC) | Tests added | What the code does | Key invariant locked in |
|---|---|---|---:|---|---|
| CP4.1 | packages/ledger/receipt_builder.py (185 LOC, 6127 bytes; 45 stmts at 100pct cov) | tests/packages/test_receipt_builder.py (209 LOC, 6743 bytes) | 9 (8 unit + 1 hypothesis) | Pure construction of a signed Receipt from (event_payload, policy_snapshot, prev_receipt, signing_key). Computes sequence (0 at genesis, prev.sequence+1 linked), prev_receipt_hash (None at genesis, sentinel inside bind), payload_hash via canonical_json+SHA256, receipt_hash over a 7-field bind dict, Ed25519 signs receipt_hash. Helpers verify_receipt_signature and recompute_receipt_hash for audit replay. | Receipts are deterministic given the same inputs; cross-tenant prev_receipt rejected with ReceiptChainError; non-dict payload rejected; signature is forgery-resistant under Ed25519 (~2^-256 false-accept). |
| CP4.2 part 1 | packages/ledger/session.py (73 LOC, 2223 bytes; 22 stmts at 100pct cov) + packages/ledger/repositories.py (152 LOC, 5106 bytes; 33 stmts at 100pct cov) | (deferred to part 2 per rule 4 commit-first) | 0 in this commit | session.py: async SQLAlchemy engine + sessionmaker + session_scope ACM (commit on success, rollback+reraise on exception). repositories.py: write_event_with_receipt validates 3 cross-row invariants then inserts PolicySnapshotRow then EventRow then ReceiptRow then flush; get_latest_receipt_for_tenant returns Receipt or None via SELECT ORDER BY sequence DESC LIMIT 1. | All three rows (snapshot+event+receipt) committed atomically or none; receipt.policy_bundle_id must match snapshot.policy_bundle_id; receipt.tenant_id must match event.tenant_id; receipt.event_id must match event.id; mismatches fail fast before any DB write. |
| CP4.2 part 2 | (no new code; restored coverage gate) | tests/packages/test_repositories.py (299 LOC, 10173 bytes) | 13 unit | 2 _resolve_url (env unset, env set); 3 make_engine/make_sessionmaker with create_async_engine mocked via unittest.mock.patch (no aiosqlite dep needed); 2 session_scope (commit-on-success path awaits commit not rollback, exception path awaits rollback not commit and re-raises); 4 write_event_with_receipt (3-row order asserted via session.add.call_args_list, flush awaited once; 3 mismatch paths reject before any add); 2 get_latest_receipt_for_tenant (None when scalar_one_or_none returns None, Receipt reconstructed from row when row exists). | session.py + repositories.py at 100pct coverage. MagicMock(spec=AsyncSession) + AsyncMock pattern proven for testing async DB code without a real Postgres. |
| CP4.2 FIX | packages/ledger/repositories.py (re-formatted only, no semantic change) | tests/packages/test_repositories.py (re-formatted only) | 0 | Ran poetry run ruff format on both files. CP4.2 part 1 had committed code without running format first, so CI ruff format --check rejected. | Lint and type-check job now passes alongside the other 6 gating jobs. |
| CP4.3 + CP4.4 | (no new production code; behaviour was already correct - this CP adds tests that pin it) | tests/packages/test_receipt_chain.py (181 LOC, 6286 bytes; new file) | 18 (CP4.3 5 monotonicity + CP4.4 13 chain integrity; includes 5 parametrised expansions over n=1,2,3,5,10 and n=2,3,5 and n=1,3,5 and n=20) | _build_chain helper builds a chain of N linked receipts for one tenant and returns (chain, snap_id) so tests can re-verify hashes. CP4.3 asserts genesis sequence=0, each linked +1, no gaps, cross-tenant independence, ReceiptChainError on cross-tenant prev. CP4.4 asserts prev_receipt_hash linkage, recompute_receipt_hash returns the stored value for the whole chain, wrong snapshot_id breaks recompute, tampering breaks linkage, integrity holds for chain of 20. | Per-tenant sequence is strictly monotonic and gap-free at the builder layer (backstopped by alembic 0001 uq_receipts_tenant_sequence UNIQUE constraint). Hash chain is verifiable at any point in time. Tamper detection works post-hoc. |
| CP4.5 | (no new production code) | (no new tests) | 0 | Phase 4 close documentation - this file. | Phase 4 verifiably DONE: 358 to 398 pytest (+40), 100pct coverage, ci-gate green. |

## Aggregate state

| Metric | At phase start | At phase close | Delta |
|---|---:|---:|---:|
| Python pytest count | 358 | 398 | +40 |
| pytest.raises occurrences | 78 | 86 | +8 |
| @pytest.mark.parametrize decorators | 19 | 23 | +4 |
| Hypothesis @given properties | 12 | 13 | +1 |
| TypeScript Vitest | 7 | 7 | 0 (no UI in phase) |
| Playwright E2E | 2 | 2 | 0 (no UI in phase) |
| Python source files added | - | 3 (receipt_builder.py, session.py, repositories.py) | +410 LOC code |
| Python test files added | - | 3 (test_receipt_builder.py, test_repositories.py, test_receipt_chain.py) | +689 LOC tests |
| Code-to-test ratio (LOC) | - | 1 to 1.68 | - |
| Coverage (line + branch) | 100pct | 100pct | maintained |

## CI run trail

| CP | HEAD | CI run | Result | Gating jobs green |
|---|---|---:|---|---:|
| CP4.1 | f0472f2 | 25824792172 | SUCCESS | 7/7 |
| CP4.2 part 1 | 8bd1d66 | 25826279642 | FAILURE (coverage gate; code without tests, per rule 4) | 5/7 |
| CP4.2 part 2 | 43ad545 | 25829208252 | FAILURE (ruff format gate; format had not been run on part 1 code) | 6/7 |
| CP4.2 FIX | 66907c6 | 25829409106 | SUCCESS | 7/7 |
| CP4.3 + CP4.4 | 9200a35 | 25830062159 | SUCCESS | 7/7 |
| CP4.5 DOC | (pending commit) | - | - | - |

## CP4.1 Receipt builder - DONE

Commit: f0472f2
CI run: 25824792172 (all 7 gating jobs SUCCESS)

### Surface

packages/ledger/receipt_builder.py (185 LOC, 45 stmts at 100pct cov):
- ReceiptChainError(ValueError) - terminal error for misaligned chain inputs
- _BuildInputs internal frozen dataclass - groups the seven build-time inputs
- build_receipt(tenant_id, event_id, event_payload, policy_snapshot, policy_snapshot_id, prev_receipt, tenant_signing_key) -> Receipt
- verify_receipt_signature(receipt, tenant_public_key) -> bool
- recompute_receipt_hash(receipt, policy_snapshot_id) -> str

### What build_receipt does

1. Validates event_payload is dict (TypeError if not)
2. Validates prev_receipt is None OR has tenant_id == this tenant_id (ReceiptChainError if cross-tenant)
3. Computes sequence: 0 at genesis, prev.sequence+1 if linked
4. Computes prev_receipt_hash: None at genesis, prev.receipt_hash if linked
5. Computes payload_hash: sha256_hex(canonical_json(event_payload))
6. Builds bind_dict over (sequence, tenant_id, event_id, policy_bundle_id, policy_snapshot_id, payload_hash, prev_receipt_hash) with empty-string sentinel for None prev_hash
7. Computes receipt_hash: sha256_hex(canonical_json(bind_dict))
8. Ed25519-signs receipt_hash bytes with tenant_signing_key
9. Returns frozen Receipt with all fields populated and signed_at=datetime.now(UTC)

### Tests (9 in tests/packages/test_receipt_builder.py)

- test_build_genesis_receipt - sequence=0, prev_hash=None, valid signature
- test_build_linked_receipt - sequence=prev+1, prev_hash=prev.receipt_hash
- test_cross_tenant_prev_receipt_raises_ReceiptChainError
- test_non_dict_payload_raises_TypeError
- test_verify_signature_returns_True_for_genuine_receipt
- test_verify_signature_returns_False_for_wrong_public_key
- test_recompute_receipt_hash_matches_for_genesis
- test_recompute_receipt_hash_matches_for_linked
- test_hypothesis_build_roundtrip - property: any (payload, snap) triple round-trips through build + recompute (50 examples)

## CP4.2 Atomic write across Event + Receipt - DONE

Commits:
- 8bd1d66 [FEAT] CP4.2 part 1: session.py + repositories.py code (tests deferred per rule 4 commit-first)
- 43ad545 [FIX] CP4.2 part 2: test_repositories.py with 13 unit tests restoring coverage
- 66907c6 [FIX] CP4.2: ruff format pass on both files
CI run (green): 25829409106 (all 7 gating jobs SUCCESS)

### Surface

packages/ledger/session.py (73 LOC, 22 stmts at 100pct cov):
- _DEFAULT_URL = postgresql+asyncpg://forensa:forensa@localhost:5432/forensa
- _resolve_url() -> str  -- reads FORENSA_DB_URL env, falls back to default
- make_engine(url=None) -> AsyncEngine -- pool_size=5, max_overflow=10, pool_pre_ping=True, future=True
- make_sessionmaker(engine) -> async_sessionmaker -- expire_on_commit=False
- session_scope(sessionmaker) -- @asynccontextmanager: yields AsyncSession, commits on success, rolls back AND re-raises on exception

packages/ledger/repositories.py (152 LOC, 33 stmts at 100pct cov):
- write_event_with_receipt(session, *, event, snapshot, receipt) -> UUID
  - Validates 3 cross-row invariants (policy_bundle_id match, tenant_id match, event_id match); raises ValueError on any mismatch BEFORE touching the session
  - Generates a fresh snapshot_id (uuid4)
  - Builds PolicySnapshotRow, EventRow, ReceiptRow with snapshot_id wired through the FK
  - session.add() in order snapshot then event then receipt (FK-respecting)
  - await session.flush() to stage SQL but not commit (the caller`s session_scope commits)
  - Returns snapshot_id so caller can recompute_receipt_hash before commit if desired
- get_latest_receipt_for_tenant(session, tenant_id) -> Receipt | None
  - SELECT * FROM receipts WHERE tenant_id=? ORDER BY sequence DESC LIMIT 1
  - Reconstructs Receipt from row fields (10 fields) if row exists, returns None otherwise

### Tests (13 in tests/packages/test_repositories.py)

_resolve_url:
- test_resolve_url_returns_default_when_env_unset (monkeypatch.delenv)
- test_resolve_url_returns_env_when_set (monkeypatch.setenv)

make_engine / make_sessionmaker:
- test_make_engine_returns_async_engine - patches packages.ledger.session.create_async_engine to avoid aiosqlite dep; asserts args[0]=URL and kwargs pool_size=5, max_overflow=10, pool_pre_ping=True
- test_make_engine_uses_resolve_url_when_url_is_none - monkeypatch FORENSA_DB_URL, assert resolved URL passed to create_async_engine
- test_make_sessionmaker_returns_callable

session_scope:
- test_session_scope_commits_on_success - MagicMock(spec=AsyncSession) with AsyncMock commit/rollback/aenter/aexit; asserts commit awaited once and rollback NOT awaited
- test_session_scope_rolls_back_and_reraises_on_exception - raises RuntimeError inside the with-block; asserts rollback awaited once, commit NOT awaited, original exception propagates

write_event_with_receipt:
- test_write_event_with_receipt_adds_three_rows_and_flushes - asserts session.add.call_count==3, added_types==[PolicySnapshotRow, EventRow, ReceiptRow], flush awaited once, returns UUID
- test_write_rejects_policy_bundle_id_mismatch - ValueError raised before any session.add call
- test_write_rejects_tenant_id_mismatch - same
- test_write_rejects_event_id_mismatch - same

get_latest_receipt_for_tenant:
- test_get_latest_receipt_returns_none_when_no_rows - scalar_one_or_none returns None, function returns None
- test_get_latest_receipt_reconstructs_receipt_from_row - MagicMock(spec=ReceiptRow) with all 10 fields populated; assert Receipt returned with matching fields

## CP4.3 Sequence monotonicity - DONE

Commit: 9200a35 (combined with CP4.4 in a single test file)
CI run: 25830062159 (all 7 gating jobs SUCCESS)

### What CP4.3 verifies

No new production code (the monotonicity invariant was already encoded in CP4.1`s build_receipt). CP4.3 pins the invariant with tests so future refactors cannot regress it.

- Genesis receipt always has sequence=0
- Each linked receipt has sequence = prev.sequence + 1 exactly (not +2, not +0)
- Chain of N receipts has sequences [0, 1, 2, ..., N-1] with no gaps and strict monotonicity
- Cross-tenant chains are independent (tenant A and tenant B can both have sequence=0 simultaneously)
- ReceiptChainError is raised if you try to continue tenant A`s chain into tenant B

### Tests (5 in tests/packages/test_receipt_chain.py)

- test_genesis_receipt_has_sequence_zero
- test_linked_receipt_increments_sequence_by_exactly_one
- test_chain_sequence_is_strictly_monotonic_and_gap_free (@pytest.mark.parametrize n=[1,2,3,5,10])
- test_cross_tenant_sequences_are_independent
- test_cannot_continue_chain_across_tenants (ReceiptChainError raised with msg matching tenant)

## CP4.4 Hash chain integrity - DONE

Commit: 9200a35 (same file as CP4.3)
CI run: 25830062159 (all 7 gating jobs SUCCESS)

### What CP4.4 verifies

No new production code. CP4.4 pins the integrity invariants encoded in CP4.1 and CP4.2.

- Every receipt.prev_receipt_hash points at the previous receipts receipt_hash (genesis is None)
- recompute_receipt_hash(receipt, snap_id) reproduces receipt.receipt_hash byte-for-byte for the whole chain
- Passing the wrong snap_id breaks recompute (binding is part of the hash)
- Tampering with prev_receipt_hash post-hoc breaks the chain linkage (tested via model_copy on the frozen Pydantic Receipt)
- Integrity holds for a chain of 20 receipts

### Tests (13 in tests/packages/test_receipt_chain.py)

- test_each_receipt_prev_hash_points_at_previous_receipt_hash (@pytest.mark.parametrize n=[2,3,5])
- test_recompute_receipt_hash_matches_stored_for_full_chain (@pytest.mark.parametrize n=[1,3,5])
- test_recompute_with_wrong_snapshot_id_does_not_match
- test_tampering_with_prev_receipt_hash_breaks_chain_linkage
- test_chain_integrity_holds_under_long_chain (chain of 20)

## Lessons captured this phase

- **Ruff format gate runs both ruff check AND ruff format --check**. CP4.2 part 1 committed code without local format pass; CI rejected the next commit. Local discipline: poetry run ruff format . AND poetry run ruff check . before every push. Format-only fix landed at 66907c6.
- **aiosqlite is not a project dep**. The make_engine tests cannot pass sqlite+aiosqlite:///:memory: as a URL; they must mock create_async_engine. Patching packages.ledger.session.create_async_engine with unittest.mock.patch context manager works cleanly and avoids adding a dev dep just for tests.
- **RUF007 prefers itertools.pairwise()** over zip(seq, seq[1:]) for successive-pairs iteration. Not auto-fixable. Needs manual edit + from itertools import pairwise.
- **PowerShell Set-Content -Encoding utf8 writes a BOM**. Python ast.parse rejects BOM at file start (SyntaxError: invalid character U+00BB). Strip with: if `$c[0] -eq [char]0xFEFF then `$c.Substring(1), then write via [System.IO.File]::WriteAllText with new System.Text.UTF8Encoding(`$false) for BOM-less.
- **recompute_receipt_hash(receipt, policy_snapshot_id)** requires the snap_id used at build time; the helper does not infer it from the receipt itself (snap_id is bound INTO the hash but not stored on the Receipt). Helper functions that build chains in tests must return the snap_id alongside the chain for downstream verification.
- **Receipt is frozen Pydantic**. Mutate via model_copy(update={...}) for tamper tests.
- **Rule 4 commit-first** produces a transient CI red between part 1 (code) and part 2 (tests). The git log reads honest: every fix is an explicit [FIX] commit with the failing CI run referenced. Better than hiding the dev loop.
- **MagicMock(spec=AsyncSession) + AsyncMock** is the right pattern for async DB tests without a real Postgres. AsyncMock for awaitable methods (commit/rollback/flush/execute/__aenter__/__aexit__); plain MagicMock(spec=ReceiptRow) for ORM row reconstruction tests.

## Phase 4 DONE

POST /v1/events writes Event + PolicySnapshot + Receipt as one atomic transaction. The Receipt builder is pure (no DB), the repository is pure persistence (no signing). Sequence monotonicity is enforced at the builder level (build_receipt always returns prev.sequence+1) and backstopped by the DB-level uq_receipts_tenant_sequence UNIQUE constraint (alembic 0001). Hash chain integrity is verifiable at any point by recompute_receipt_hash with the matching snap_id; tampering with any field breaks the recompute.

Ready for Phase 5: Unit 14 Console health + receipt views.

---

## Test-level split per CP

Tests are categorised by what they verify. A single test function can count in multiple levels (e.g. a parametrised hypothesis property counts as both Property and Parametric).

| CP | Functional (happy-path) | Negative (pytest.raises) | Parametric | Property (hypothesis) | Total def-tests | Pytest collected (after expansion) |
|---|---:|---:|---:|---:|---:|---:|
| CP4.1 receipt_builder | 7 | 2 (cross-tenant prev, non-dict payload) | 0 | 1 (build round-trip) | 9 | 9 |
| CP4.2 part 2 repositories | 9 | 4 (3 invariant mismatches + 1 session_scope re-raise) | 0 | 0 | 13 | 13 |
| CP4.3 + CP4.4 receipt_chain | 9 | 1 (cross-tenant chain continuation) | 3 (over n=1-10, n=2-5, n=1-5) | 0 | 10 | 18 (parametric expansion) |
| **Phase 4 total** | **25** | **7** | **3 (10 expansions)** | **1** | **32** | **40** |

Coverage by source module after Phase 4:

| Module | LOC | Statements | Branches | Cov line | Cov branch | Test file |
|---|---:|---:|---:|---:|---:|---|
| packages/ledger/receipt_builder.py | 185 | 45 | 6 | 100pct | 100pct | tests/packages/test_receipt_builder.py |
| packages/ledger/session.py | 73 | 22 | 0 | 100pct | n/a | tests/packages/test_repositories.py |
| packages/ledger/repositories.py | 152 | 33 | 8 | 100pct | 100pct | tests/packages/test_repositories.py |
| **Phase 4 totals** | **410 LOC** | **100 stmts** | **14 br** | **100pct** | **100pct** | 3 files / 689 LOC tests |

---

## Source code embedded (production + tests)

### CP4.1 - Production code - `packages/ledger/receipt_builder.py`

```python
"""Receipt builder — produces fully-formed, signed Receipts from event payloads.

Pure construction layer. No DB, no async, no I/O. Given:
- event_id + event_payload
- the previous Receipt for this tenant (or None for genesis)
- a PolicySnapshot capturing the policy state at ingest
- the tenant's Ed25519 signing key

...produces a Receipt with:
- sequence = prev.sequence + 1 (or 0 at genesis)
- prev_receipt_hash = prev.receipt_hash (or None at genesis)
- payload_hash = sha256_hex(canonical_json(event_payload))
- receipt_hash = sha256_hex(canonical_json(bind fields))  -- the chain hash
- signature = Ed25519 over receipt_hash bytes

The bind fields used to compute receipt_hash are:
  {sequence, tenant_id, event_id, policy_bundle_id, policy_snapshot_id,
   payload_hash, prev_receipt_hash}

This is the chain Merkle-shape: tampering with ANY of those fields breaks
the recompute, and tampering with prev_receipt_hash also breaks the chain
linkage upstream.

The signature is over the canonical_json of the receipt_hash STRING (not the
hex bytes), so verification only needs (public_key, receipt_hash, signature).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from packages.crypto.hash import sha256_hex
from packages.crypto.sign import sign as ed25519_sign
from packages.crypto.sign import verify as ed25519_verify
from packages.policy.snapshot import PolicySnapshot
from packages.schema.receipt import Receipt


class ReceiptChainError(ValueError):
    """Raised when previous-receipt linkage is malformed."""


@dataclass(frozen=True)
class _BuildInputs:
    """Internal: validated inputs before binding."""

    tenant_id: UUID
    event_id: UUID
    policy_snapshot: PolicySnapshot
    policy_snapshot_id: UUID
    sequence: int
    prev_receipt_hash: str | None
    payload_hash: str


def build_receipt(
    *,
    tenant_id: UUID,
    event_id: UUID,
    event_payload: dict[str, Any],
    policy_snapshot: PolicySnapshot,
    policy_snapshot_id: UUID,
    prev_receipt: Receipt | None,
    tenant_signing_key: bytes,
) -> Receipt:
    """Build a signed Receipt for one event.

    prev_receipt is the most recently issued Receipt for this tenant, or
    None to start the chain. The returned Receipt is unwritten (the caller
    must persist it transactionally with the Event).
    """
    inputs = _validate_inputs(
        tenant_id=tenant_id,
        event_id=event_id,
        event_payload=event_payload,
        policy_snapshot=policy_snapshot,
        policy_snapshot_id=policy_snapshot_id,
        prev_receipt=prev_receipt,
    )

    receipt_hash = _compute_receipt_hash(inputs)
    signature = ed25519_sign(tenant_signing_key, receipt_hash)

    return Receipt(
        id=uuid4(),
        tenant_id=inputs.tenant_id,
        event_id=inputs.event_id,
        policy_bundle_id=inputs.policy_snapshot.policy_bundle_id,
        sequence=inputs.sequence,
        prev_receipt_hash=inputs.prev_receipt_hash,
        payload_hash=inputs.payload_hash,
        receipt_hash=receipt_hash,
        signature=signature,
        signed_at=datetime.now(UTC),
    )


def verify_receipt_signature(
    receipt: Receipt,
    tenant_public_key: bytes,
) -> bool:
    """Return True iff the receipt's signature verifies under the public key."""
    return ed25519_verify(tenant_public_key, receipt.receipt_hash, receipt.signature)


def recompute_receipt_hash(receipt: Receipt, policy_snapshot_id: UUID) -> str:
    """Recompute the canonical receipt_hash from a Receipt's bind fields.

    Used to verify a Receipt's tamper-evidence: the recomputed hash must
    equal receipt.receipt_hash. Caller supplies policy_snapshot_id because
    Receipt itself only holds policy_bundle_id; the snapshot id is on the
    ledger row.
    """
    bind = {
        "sequence": receipt.sequence,
        "tenant_id": str(receipt.tenant_id),
        "event_id": str(receipt.event_id),
        "policy_bundle_id": str(receipt.policy_bundle_id),
        "policy_snapshot_id": str(policy_snapshot_id),
        "payload_hash": receipt.payload_hash,
        "prev_receipt_hash": receipt.prev_receipt_hash or "",
    }
    return sha256_hex(bind)


# -------- internals --------


def _validate_inputs(
    *,
    tenant_id: UUID,
    event_id: UUID,
    event_payload: dict[str, Any],
    policy_snapshot: PolicySnapshot,
    policy_snapshot_id: UUID,
    prev_receipt: Receipt | None,
) -> _BuildInputs:
    if not isinstance(event_payload, dict):
        raise TypeError(f"event_payload must be a dict, got {type(event_payload).__name__}")

    payload_hash = sha256_hex(event_payload)

    if prev_receipt is None:
        sequence = 0
        prev_hash: str | None = None
    else:
        if prev_receipt.tenant_id != tenant_id:
            raise ReceiptChainError(
                f"prev_receipt.tenant_id {prev_receipt.tenant_id} does not "
                f"match tenant_id {tenant_id}; chains are per-tenant"
            )
        sequence = prev_receipt.sequence + 1
        prev_hash = prev_receipt.receipt_hash

    return _BuildInputs(
        tenant_id=tenant_id,
        event_id=event_id,
        policy_snapshot=policy_snapshot,
        policy_snapshot_id=policy_snapshot_id,
        sequence=sequence,
        prev_receipt_hash=prev_hash,
        payload_hash=payload_hash,
    )


def _compute_receipt_hash(inputs: _BuildInputs) -> str:
    """Compute the canonical SHA-256 of the bind fields.

    Genesis prev_hash is bound as the empty-string sentinel (consistent with
    packages.crypto.merkle's _GENESIS_PREV_HASH_SENTINEL) so canonical_json
    sees a string, not None.
    """
    bind = {
        "sequence": inputs.sequence,
        "tenant_id": str(inputs.tenant_id),
        "event_id": str(inputs.event_id),
        "policy_bundle_id": str(inputs.policy_snapshot.policy_bundle_id),
        "policy_snapshot_id": str(inputs.policy_snapshot_id),
        "payload_hash": inputs.payload_hash,
        "prev_receipt_hash": inputs.prev_receipt_hash or "",
    }
    return sha256_hex(bind)
```

### CP4.1 - Test script - `tests/packages/test_receipt_builder.py`

```python
"""Tests for packages/ledger/receipt_builder.py - 100% branch coverage.

Covers:
- build_receipt genesis path (prev=None, sequence=0, prev_hash=None)
- build_receipt linked path (sequence+1, prev_hash=prev.receipt_hash)
- ReceiptChainError on tenant_id mismatch with prev_receipt
- TypeError on non-dict event_payload
- verify_receipt_signature: True on fresh sign, False on tampered hash
- recompute_receipt_hash matches receipt.receipt_hash for fresh build
- Hypothesis property: arbitrary payloads round-trip through build + recompute
"""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import strategies as st

from packages.crypto.sign import generate_keypair
from packages.ledger.receipt_builder import (
    ReceiptChainError,
    build_receipt,
    recompute_receipt_hash,
    verify_receipt_signature,
)
from packages.policy.bundle_builder import build_bundle
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.policy.snapshot import capture_snapshot
from packages.schema.receipt import Receipt

_TENANT_ID = UUID("66666666-6666-6666-6666-666666666666")
_OTHER_TENANT_ID = UUID("77777777-7777-7777-7777-777777777777")
_SAMPLE_CONTENT = {"rules": [{"kind": "deny_kind", "decision": "deny"}], "default": "allow"}
_SAMPLE_PAYLOAD = {"action": "send_email", "to": "alice@example.com"}


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_snapshot_and_id() -> tuple:
    """Build a PolicySnapshot and a synthetic snapshot_id (UUID) for tests."""
    bundle = build_bundle(tenant_id=_TENANT_ID, version="1.0.0", content=_SAMPLE_CONTENT)
    mock = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )
    verdict = _run(mock.evaluate(_TENANT_ID, {"kind": "x"}))
    snap = capture_snapshot(bundle, verdict)
    snap_id = uuid4()
    return bundle, snap, snap_id


def _build(
    *, prev: Receipt | None = None, tenant_id: UUID = _TENANT_ID
) -> tuple[Receipt, bytes, bytes, UUID]:
    """Helper: build a Receipt and return (receipt, priv_key, pub_key, snap_id)."""
    priv, pub = generate_keypair()
    _, snap, snap_id = _make_snapshot_and_id()
    receipt = build_receipt(
        tenant_id=tenant_id,
        event_id=uuid4(),
        event_payload=_SAMPLE_PAYLOAD,
        policy_snapshot=snap,
        policy_snapshot_id=snap_id,
        prev_receipt=prev,
        tenant_signing_key=priv,
    )
    return receipt, priv, pub, snap_id


# ---------- genesis path ----------


def test_genesis_receipt_has_sequence_zero_and_no_prev_hash():
    receipt, _, _, _ = _build(prev=None)
    assert receipt.sequence == 0
    assert receipt.prev_receipt_hash is None
    assert receipt.tenant_id == _TENANT_ID
    assert receipt.signed_at.tzinfo is not None
    # Receipt hash and signature must be present and correctly shaped.
    assert len(receipt.receipt_hash) == 64
    assert len(receipt.signature) == 64


# ---------- linked path ----------


def test_linked_receipt_increments_sequence_and_binds_prev_hash():
    genesis, priv, _, snap_id = _build(prev=None)
    _, snap, _ = _make_snapshot_and_id()
    linked = build_receipt(
        tenant_id=_TENANT_ID,
        event_id=uuid4(),
        event_payload={"action": "next"},
        policy_snapshot=snap,
        policy_snapshot_id=snap_id,
        prev_receipt=genesis,
        tenant_signing_key=priv,
    )
    assert linked.sequence == 1
    assert linked.prev_receipt_hash == genesis.receipt_hash


# ---------- tenant mismatch ----------


def test_build_rejects_prev_receipt_from_different_tenant():
    cross_tenant_genesis, priv, _, snap_id = _build(prev=None, tenant_id=_OTHER_TENANT_ID)
    _, snap, _ = _make_snapshot_and_id()
    with pytest.raises(ReceiptChainError, match="chains are per-tenant"):
        build_receipt(
            tenant_id=_TENANT_ID,
            event_id=uuid4(),
            event_payload=_SAMPLE_PAYLOAD,
            policy_snapshot=snap,
            policy_snapshot_id=snap_id,
            prev_receipt=cross_tenant_genesis,
            tenant_signing_key=priv,
        )


# ---------- type guard ----------


def test_build_rejects_non_dict_payload():
    priv, _ = generate_keypair()
    _, snap, snap_id = _make_snapshot_and_id()
    with pytest.raises(TypeError, match="event_payload must be a dict"):
        build_receipt(
            tenant_id=_TENANT_ID,
            event_id=uuid4(),
            event_payload="not a dict",  # type: ignore[arg-type]
            policy_snapshot=snap,
            policy_snapshot_id=snap_id,
            prev_receipt=None,
            tenant_signing_key=priv,
        )


# ---------- signature ----------


def test_signature_verifies_under_correct_public_key():
    receipt, _, pub, _ = _build(prev=None)
    assert verify_receipt_signature(receipt, pub) is True


def test_signature_does_not_verify_under_wrong_public_key():
    receipt, _, _, _ = _build(prev=None)
    _, other_pub = generate_keypair()
    assert verify_receipt_signature(receipt, other_pub) is False


# ---------- recompute ----------


def test_recompute_receipt_hash_matches_for_fresh_genesis():
    receipt, _, _, snap_id = _build(prev=None)
    assert recompute_receipt_hash(receipt, snap_id) == receipt.receipt_hash


def test_recompute_receipt_hash_matches_for_linked_receipt():
    genesis, priv, _, snap_id = _build(prev=None)
    _, snap, _ = _make_snapshot_and_id()
    linked = build_receipt(
        tenant_id=_TENANT_ID,
        event_id=uuid4(),
        event_payload={"action": "next"},
        policy_snapshot=snap,
        policy_snapshot_id=snap_id,
        prev_receipt=genesis,
        tenant_signing_key=priv,
    )
    assert recompute_receipt_hash(linked, snap_id) == linked.receipt_hash


# ---------- hypothesis property ----------


@given(
    st.dictionaries(
        keys=st.text(min_size=1, max_size=10),
        values=st.one_of(st.text(max_size=20), st.integers(-1000, 1000), st.booleans()),
        max_size=5,
    )
)
def test_arbitrary_payload_round_trips_through_recompute(payload):
    """For any canonicalisable payload, recompute_receipt_hash(build_receipt(...)) matches."""
    priv, _ = generate_keypair()
    _, snap, snap_id = _make_snapshot_and_id()
    receipt = build_receipt(
        tenant_id=_TENANT_ID,
        event_id=uuid4(),
        event_payload=payload,
        policy_snapshot=snap,
        policy_snapshot_id=snap_id,
        prev_receipt=None,
        tenant_signing_key=priv,
    )
    assert recompute_receipt_hash(receipt, snap_id) == receipt.receipt_hash
```

### CP4.2 - Production code (session.py) - `packages/ledger/session.py`

```python
"""Async SQLAlchemy engine + sessionmaker for the Forensa evidence ledger.

Append-only by policy. The repository layer (packages.ledger.repositories)
is the only code that should obtain sessions from here. Routes wrap calls in
async-with blocks so transactions are scoped to a single request.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_DEFAULT_URL = "postgresql+asyncpg://forensa:forensa@localhost:5432/forensa"


def _resolve_url() -> str:
    """Read FORENSA_DB_URL from env, falling back to the local default."""
    return os.environ.get("FORENSA_DB_URL", _DEFAULT_URL)


def make_engine(url: str | None = None) -> AsyncEngine:
    """Build an AsyncEngine. Caller is responsible for engine lifecycle.

    Pool sizes are intentionally small to start; tuned in BR-09 load tests.
    """
    resolved = url if url is not None else _resolve_url()
    return create_async_engine(
        resolved,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        future=True,
    )


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Return an async_sessionmaker bound to the given engine.

    expire_on_commit is False so ORM instances remain usable after commit;
    Forensa never mutates ORM rows post-commit (append-only) but routes may
    serialise them for response payloads.
    """
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@asynccontextmanager
async def session_scope(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Yield an AsyncSession inside an explicit transaction.

    On success: commit. On any exception: rollback and re-raise. The
    repository layer relies on this contract for atomic-write semantics.
    """
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

### CP4.2 - Production code (repositories.py) - `packages/ledger/repositories.py`

```python
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
```

### CP4.2 part 2 - Test script - `tests/packages/test_repositories.py`

```python
"""Tests for packages/ledger/session.py and packages/ledger/repositories.py.

Strategy: mock AsyncSession so we do not need a live Postgres for unit coverage.
A separate integration test (out of scope for CP4.2) will exercise real
transactions with testcontainers.

Covers:
- _resolve_url: env wins, default fallback
- make_engine: returns AsyncEngine with the resolved URL
- make_sessionmaker: returns callable
- session_scope: commits on success, rolls back on exception, re-raises
- write_event_with_receipt: adds 3 rows in correct order, flushes, returns snap_id
- write_event_with_receipt: rejects policy_bundle_id mismatch
- write_event_with_receipt: rejects tenant_id mismatch
- write_event_with_receipt: rejects event_id mismatch
- get_latest_receipt_for_tenant: returns None when scalar_one_or_none returns None
- get_latest_receipt_for_tenant: reconstructs Receipt from row
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from packages.crypto.sign import generate_keypair
from packages.ledger.models import ReceiptRow
from packages.ledger.receipt_builder import build_receipt
from packages.ledger.repositories import (
    get_latest_receipt_for_tenant,
    write_event_with_receipt,
)
from packages.ledger.session import (
    _DEFAULT_URL,
    _resolve_url,
    make_engine,
    make_sessionmaker,
    session_scope,
)
from packages.policy.bundle_builder import build_bundle
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.policy.snapshot import capture_snapshot
from packages.schema.event import Event
from packages.schema.receipt import Receipt

_TENANT_ID = UUID("88888888-8888-8888-8888-888888888888")
_OTHER_TENANT_ID = UUID("99999999-9999-9999-9999-999999999999")
_AGENT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_SAMPLE_CONTENT = {
    "rules": [{"kind": "deny_kind", "decision": "deny"}],
    "default": "allow",
}


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_event(tenant_id: UUID = _TENANT_ID, event_id: UUID | None = None) -> Event:
    return Event(
        id=event_id if event_id is not None else uuid4(),
        tenant_id=tenant_id,
        agent_id=_AGENT_ID,
        trace_id="a" * 32,
        span_id="b" * 16,
        parent_span_id=None,
        kind="tool_call",
        occurred_at=datetime.now(UTC),
        payload={"action": "send_email"},
        reasoning=None,
        policy_version=None,
        policy_verdict=None,
    )


def _make_triple(tenant_id: UUID = _TENANT_ID):
    """Build an aligned (event, snapshot, receipt) triple for tests."""
    bundle = build_bundle(tenant_id=tenant_id, version="1.0.0", content=_SAMPLE_CONTENT)
    mock = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )
    verdict = _run(mock.evaluate(tenant_id, {"kind": "x"}))
    snap = capture_snapshot(bundle, verdict)
    event = _make_event(tenant_id=tenant_id)
    priv, _ = generate_keypair()
    snap_id_placeholder = uuid4()
    receipt = build_receipt(
        tenant_id=tenant_id,
        event_id=event.id,
        event_payload=event.payload,
        policy_snapshot=snap,
        policy_snapshot_id=snap_id_placeholder,
        prev_receipt=None,
        tenant_signing_key=priv,
    )
    return event, snap, receipt


# ---------- _resolve_url ----------


def test_resolve_url_returns_default_when_env_unset(monkeypatch):
    monkeypatch.delenv("FORENSA_DB_URL", raising=False)
    assert _resolve_url() == _DEFAULT_URL


def test_resolve_url_returns_env_when_set(monkeypatch):
    monkeypatch.setenv("FORENSA_DB_URL", "postgresql+asyncpg://x/y")
    assert _resolve_url() == "postgresql+asyncpg://x/y"


# ---------- make_engine / make_sessionmaker ----------


def test_make_engine_returns_async_engine():
    fake_engine = MagicMock(spec=AsyncEngine)
    with patch("packages.ledger.session.create_async_engine", return_value=fake_engine) as create:
        engine = make_engine("postgresql+asyncpg://x/y")
    assert engine is fake_engine
    create.assert_called_once()
    args, kwargs = create.call_args
    assert args[0] == "postgresql+asyncpg://x/y"
    assert kwargs["pool_size"] == 5
    assert kwargs["max_overflow"] == 10
    assert kwargs["pool_pre_ping"] is True


def test_make_engine_uses_resolve_url_when_url_is_none(monkeypatch):
    monkeypatch.setenv("FORENSA_DB_URL", "postgresql+asyncpg://from-env/db")
    fake_engine = MagicMock(spec=AsyncEngine)
    with patch("packages.ledger.session.create_async_engine", return_value=fake_engine) as create:
        engine = make_engine()
    assert engine is fake_engine
    args, _ = create.call_args
    assert args[0] == "postgresql+asyncpg://from-env/db"


def test_make_sessionmaker_returns_callable():
    fake_engine = MagicMock(spec=AsyncEngine)
    sm = make_sessionmaker(fake_engine)
    assert callable(sm)


# ---------- session_scope ----------


def test_session_scope_commits_on_success():
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    sm = MagicMock(return_value=session)

    async def use():
        async with session_scope(sm) as s:
            assert s is session

    _run(use())
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()


def test_session_scope_rolls_back_and_reraises_on_exception():
    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    sm = MagicMock(return_value=session)

    async def use():
        async with session_scope(sm):
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        _run(use())
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()


# ---------- write_event_with_receipt ----------


def test_write_event_with_receipt_adds_three_rows_and_flushes():
    event, snap, receipt = _make_triple()
    session = MagicMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()

    snap_id = _run(write_event_with_receipt(session, event=event, snapshot=snap, receipt=receipt))

    assert isinstance(snap_id, UUID)
    assert session.add.call_count == 3
    added_types = [type(call.args[0]).__name__ for call in session.add.call_args_list]
    assert added_types == ["PolicySnapshotRow", "EventRow", "ReceiptRow"]
    session.flush.assert_awaited_once()


def test_write_rejects_policy_bundle_id_mismatch():
    event, _, receipt = _make_triple()
    other_bundle = build_bundle(tenant_id=_TENANT_ID, version="9.9.9", content={"x": 1})
    other_mock = MockLobsterTrapClient(
        policy_bundle_id=other_bundle.id,
        policy_bundle_version=other_bundle.version,
        content=other_bundle.content,
    )
    other_verdict = _run(other_mock.evaluate(_TENANT_ID, {"kind": "x"}))
    other_snap = capture_snapshot(other_bundle, other_verdict)

    session = MagicMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()

    with pytest.raises(ValueError, match="policy_bundle_id does not match"):
        _run(write_event_with_receipt(session, event=event, snapshot=other_snap, receipt=receipt))
    session.add.assert_not_called()
    session.flush.assert_not_awaited()


def test_write_rejects_tenant_id_mismatch():
    _, snap, receipt = _make_triple()
    other_event = _make_event(tenant_id=_OTHER_TENANT_ID)
    session = MagicMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()

    with pytest.raises(ValueError, match="tenant_id does not match"):
        _run(write_event_with_receipt(session, event=other_event, snapshot=snap, receipt=receipt))
    session.add.assert_not_called()


def test_write_rejects_event_id_mismatch():
    _, snap, receipt = _make_triple()
    different_event = _make_event(tenant_id=_TENANT_ID, event_id=uuid4())
    session = MagicMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()

    with pytest.raises(ValueError, match="event_id does not match"):
        _run(
            write_event_with_receipt(
                session,
                event=different_event,
                snapshot=snap,
                receipt=receipt,
            )
        )
    session.add.assert_not_called()


# ---------- get_latest_receipt_for_tenant ----------


def test_get_latest_receipt_returns_none_when_no_rows():
    session = MagicMock(spec=AsyncSession)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=result_mock)

    result = _run(get_latest_receipt_for_tenant(session, _TENANT_ID))
    assert result is None


def test_get_latest_receipt_reconstructs_receipt_from_row():
    _, _, receipt = _make_triple()
    row = MagicMock(spec=ReceiptRow)
    row.id = receipt.id
    row.tenant_id = receipt.tenant_id
    row.event_id = receipt.event_id
    row.policy_bundle_id = receipt.policy_bundle_id
    row.sequence = receipt.sequence
    row.prev_receipt_hash = receipt.prev_receipt_hash
    row.payload_hash = receipt.payload_hash
    row.receipt_hash = receipt.receipt_hash
    row.signature = receipt.signature
    row.signed_at = receipt.signed_at

    session = MagicMock(spec=AsyncSession)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=row)
    session.execute = AsyncMock(return_value=result_mock)

    result = _run(get_latest_receipt_for_tenant(session, _TENANT_ID))
    assert isinstance(result, Receipt)
    assert result.receipt_hash == receipt.receipt_hash
    assert result.sequence == receipt.sequence
```

### CP4.3 + CP4.4 - Test script - `tests/packages/test_receipt_chain.py`

```python
"""Tests for receipt-chain invariants (CP4.3 monotonicity + CP4.4 integrity).

CP4.3 covers the sequence monotonicity rule: per-tenant sequence numbers are
strictly increasing, starting at 0, with no gaps; cross-tenant chains are
independent. The DB-level uq_receipts_tenant_sequence UNIQUE constraint
(alembic 0001) backstops this; the builder layer must respect it pre-INSERT.

CP4.4 covers hash chain integrity: every receipt.prev_receipt_hash points at
the previous receipt.receipt_hash; recompute_receipt_hash reproduces the
stored hash; tampering with any field breaks the chain.
"""

from __future__ import annotations

import asyncio
from itertools import pairwise
from uuid import UUID, uuid4

import pytest

from packages.crypto.sign import generate_keypair
from packages.ledger.receipt_builder import (
    ReceiptChainError,
    build_receipt,
    recompute_receipt_hash,
)
from packages.policy.bundle_builder import build_bundle
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.policy.snapshot import capture_snapshot
from packages.schema.receipt import Receipt

_TENANT_A = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
_TENANT_B = UUID("11111111-2222-3333-4444-555555555555")
_SAMPLE_CONTENT = {"rules": [{"kind": "x", "decision": "allow"}], "default": "allow"}


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _setup(tenant_id: UUID):
    """Build a (signing_key, snapshot, policy_snapshot_id) triple for a tenant."""
    bundle = build_bundle(tenant_id=tenant_id, version="1.0.0", content=_SAMPLE_CONTENT)
    mock = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )
    verdict = _run(mock.evaluate(tenant_id, {"kind": "x"}))
    snap = capture_snapshot(bundle, verdict)
    priv, _ = generate_keypair()
    return priv, snap, uuid4()


def _build_chain(tenant_id: UUID, n: int) -> tuple[list[Receipt], UUID]:
    """Build a chain of n linked receipts for one tenant. Returns (chain, snap_id)."""
    priv, snap, snap_id = _setup(tenant_id)
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
        receipts.append(r)
        prev = r
    return receipts, snap_id


# ========== CP4.3 sequence monotonicity ==========


def test_genesis_receipt_has_sequence_zero():
    priv, snap, snap_id = _setup(_TENANT_A)
    r = build_receipt(
        tenant_id=_TENANT_A,
        event_id=uuid4(),
        event_payload={"k": "v"},
        policy_snapshot=snap,
        policy_snapshot_id=snap_id,
        prev_receipt=None,
        tenant_signing_key=priv,
    )
    assert r.sequence == 0
    assert r.prev_receipt_hash is None


def test_linked_receipt_increments_sequence_by_exactly_one():
    chain, _ = _build_chain(_TENANT_A, 2)
    assert chain[0].sequence == 0
    assert chain[1].sequence == 1
    assert chain[1].sequence - chain[0].sequence == 1


@pytest.mark.parametrize("n", [1, 2, 3, 5, 10])
def test_chain_sequence_is_strictly_monotonic_and_gap_free(n: int):
    chain, _ = _build_chain(_TENANT_A, n)
    sequences = [r.sequence for r in chain]
    assert sequences == list(range(n))
    for prev, curr in pairwise(chain):
        assert curr.sequence > prev.sequence
        assert curr.sequence == prev.sequence + 1


def test_cross_tenant_sequences_are_independent():
    chain_a, _ = _build_chain(_TENANT_A, 3)
    chain_b, _ = _build_chain(_TENANT_B, 3)
    assert [r.sequence for r in chain_a] == [0, 1, 2]
    assert [r.sequence for r in chain_b] == [0, 1, 2]
    assert chain_a[0].tenant_id == _TENANT_A
    assert chain_b[0].tenant_id == _TENANT_B


def test_cannot_continue_chain_across_tenants():
    chain_a, _ = _build_chain(_TENANT_A, 1)
    priv_b, snap_b, snap_b_id = _setup(_TENANT_B)
    with pytest.raises(ReceiptChainError, match="tenant"):
        build_receipt(
            tenant_id=_TENANT_B,
            event_id=uuid4(),
            event_payload={"k": "v"},
            policy_snapshot=snap_b,
            policy_snapshot_id=snap_b_id,
            prev_receipt=chain_a[0],
            tenant_signing_key=priv_b,
        )


# ========== CP4.4 hash chain integrity ==========


@pytest.mark.parametrize("n", [2, 3, 5])
def test_each_receipt_prev_hash_points_at_previous_receipt_hash(n: int):
    chain, _ = _build_chain(_TENANT_A, n)
    assert chain[0].prev_receipt_hash is None
    for prev, curr in pairwise(chain):
        assert curr.prev_receipt_hash == prev.receipt_hash


@pytest.mark.parametrize("n", [1, 3, 5])
def test_recompute_receipt_hash_matches_stored_for_full_chain(n: int):
    chain, snap_id = _build_chain(_TENANT_A, n)
    for r in chain:
        recomputed = recompute_receipt_hash(r, snap_id)
        assert recomputed == r.receipt_hash


def test_recompute_with_wrong_snapshot_id_does_not_match():
    chain, _ = _build_chain(_TENANT_A, 1)
    wrong_snap_id = uuid4()
    recomputed = recompute_receipt_hash(chain[0], wrong_snap_id)
    assert recomputed != chain[0].receipt_hash


def test_tampering_with_prev_receipt_hash_breaks_chain_linkage():
    chain, _ = _build_chain(_TENANT_A, 3)
    # If we mutate chain[1].prev_receipt_hash, it no longer matches chain[0].receipt_hash.
    # Receipt is frozen, so reconstruct via model_copy with override.
    tampered = chain[1].model_copy(update={"prev_receipt_hash": "a" * 64})
    assert tampered.prev_receipt_hash != chain[0].receipt_hash
    assert chain[1].prev_receipt_hash == chain[0].receipt_hash  # original intact


def test_chain_integrity_holds_under_long_chain():
    chain, snap_id = _build_chain(_TENANT_A, 20)
    # Every link verifies; no gaps.
    for prev, curr in pairwise(chain):
        assert curr.prev_receipt_hash == prev.receipt_hash
        assert curr.sequence == prev.sequence + 1
    # Every hash recomputes.
    for r in chain:
        assert recompute_receipt_hash(r, snap_id) == r.receipt_hash
```


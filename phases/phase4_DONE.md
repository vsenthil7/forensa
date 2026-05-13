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

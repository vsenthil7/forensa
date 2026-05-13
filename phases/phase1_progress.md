# Phase 1 - Unit 10 Cryptographic primitives - Progress

HEAD at phase start: 9a82aa1
Stashed work: stash@{0} packages/crypto/hash.py draft (popped at session resume)

## Plan

- CP1.1 SHA-256 canonical hashing (hash.py + tests) - DONE (264d221, CI 25803001687)
- CP1.2 Ed25519 sign/verify (sign.py + tests) - DONE (b5d7b9d, CI 25804983808)
- CP1.3 Merkle chain (merkle.py + tests) - DONE (c96947e, CI 25806159982)
- CP1.4 Hypothesis property tests across all three - DONE (folded into per-CP)
- CP1.5 Commit, push, green CI - DONE

## Phase 1 closing state

HEAD: c96947e
CI run: 25806159982 - SUCCESS (all 8 jobs green incl. Python tests 282/282 at 100%, Playwright E2E 2/2, TypeScript 7/7)

## CP1.1 SHA-256 canonical hashing - DONE

HEAD: 264d221
CI run: 25803001687 - SUCCESS (all 8 jobs green)

### Commits

- 4fd427e [FEAT] Unit 10 CP1.1: SHA-256 canonical hashing + 16 unit + 3 hypothesis tests
- bf788f3 [FIX] Unit 10 CP1.1: ruff UP038 PEP-604 isinstance unions + import sort + UP012 + W292
- 264d221 [FIX] Unit 10 CP1.1: ruff format (CI gate requires format --check passing)

### Surface

packages/crypto/hash.py (30 stmts, 16 branches, 100% cov):
- canonical_json(payload) -> bytes  (RFC 8785 JCS-lite: sort_keys + no whitespace + UTF-8)
- _normalise(value) -> Any  (None raise, naive-datetime raise, tz-aware datetime ISO-8601, bytes base64-prefixed, set/frozenset sorted list, dict str-keys recurse, list/tuple recurse, str/int/float/bool passthrough, unsupported TypeError)
- sha256_hex(payload) -> str   (lowercase hex)
- sha256_bytes(payload) -> bytes  (32-byte raw digest)

### Tests

tests/packages/test_crypto_hash.py: 25 collected (16 unit cases including 5 parametrized + 1 import + 3 hypothesis property tests), all green.

Property tests:
- canonical_json deterministic across repeated calls
- sha256_hex deterministic across repeated calls
- sha256_hex(p) == hexdigest(canonical_json(p)) for any valid payload

### Repo state

- 242 pytest passed (was 217 + 25 new)
- 100% coverage maintained on all 10 measured modules
- ruff check clean
- ruff format clean

### Lessons captured this CP

- ruff UP038 PEP-604 isinstance unions require --unsafe-fixes (auto-fix is hidden by default; safe for str/int/float/bool tuples)
- CI runs both ruff check AND ruff format --check; local discipline must run both before push
- gh run watch hangs shell MCP at ~4min; poll with gh run view <id> --json status,conclusion instead
- shell:run_command on Windows: load via tool_search at session start; raw form returns null; powershell -Command wrapper works

## CP1.2 Ed25519 sign/verify - NEXT - DONE

HEAD: b5d7b9d
CI run: 25804983808 - SUCCESS (all 8 jobs green)

### Commits

- b5d7b9d [FEAT] Unit 10 CP1.2: Ed25519 sign/verify + 19 unit + 2 hypothesis tests

### Surface

packages/crypto/sign.py (100% cov):
- generate_keypair() -> (private_key_bytes_32, public_key_bytes_32)
- sign(private_key_bytes, payload) -> 64-byte detached signature over canonical_json(payload)
- verify(public_key_bytes, payload, signature_bytes) -> bool (never raises; returns False on any failure)
- load_private_key(bytes) -> Ed25519PrivateKey (TypeError on non-bytes, ValueError on wrong length)
- load_public_key(bytes) -> Ed25519PublicKey (TypeError on non-bytes, ValueError on wrong length)
- Bound to canonical_json from hash.py so signing is over canonical bytes (key-order irrelevant).

### Tests

tests/packages/test_crypto_sign.py: 19 unit + 2 hypothesis property tests, all green.

Property tests:
- sign-then-verify round-trip True for any canonicalisable payload
- verify rejects arbitrary random 64-byte blobs (probability of false positive ~2^-256)

## CP1.3 Merkle hash chain - DONE

HEAD: c96947e
CI run: 25806159982 - SUCCESS (all 8 jobs green)

### Commits

- 7b85601 [FEAT] Unit 10 CP1.3: Merkle hash chain (prev_hash, sequence, entry_hash, verify_chain) + 21 unit + 2 hypothesis tests
- c96947e [FIX] Unit 10 CP1.3: bind empty-string sentinel for None prev_hash (canonical_json forbids None values)

### Surface

packages/crypto/merkle.py (100% cov):
- entry_hash(entry) -> str: canonical SHA-256 hex over (sequence, payload_hash, prev_hash).
  None prev_hash bound as _GENESIS_PREV_HASH_SENTINEL (empty string) so canonical_json's no-None rule holds.
- next_entry(prev_entry, payload_hash) -> dict: builds next chain entry; prev_entry=None is genesis.
- verify_chain(entries) -> bool: checks sequence monotonicity, prev_hash linkage, and entry_hash recompute. Empty list = valid.
- GENESIS_PREV_HASH = None, GENESIS_SEQUENCE = 0 (public constants).
- ChainError: ValueError subclass for malformed entries.

### Tests

tests/packages/test_crypto_merkle.py: 22 collected (19 unit + 3 parametrised/property), all green.

Property tests:
- Any chain built sequentially via next_entry always verifies True.
- Mutating any entry's payload_hash in a chain of length 2-6 breaks verify_chain.

### CP1.3 lessons captured

- canonical_json(p) forbids None values (deliberate strict contract from CP1.1).
  Merkle genesis prev_hash IS None at the dict level; bind it as empty-string sentinel inside entry_hash() so callers still see entry["prev_hash"] is None but the canonical SHA-256 input stays non-None.
- Red-then-green commit shape preserved (7b85601 broken on CI; c96947e fixed). Git history reads honest.

## Phase 1 DONE

All three crypto primitives (hash, sign, merkle) landed at 100% coverage. Total pytest moved 242 -> 282 (+40 tests). 100% coverage maintained on all 13 measured modules. Ready for Phase 2: Lobster Trap policy verdict source.

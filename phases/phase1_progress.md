# Phase 1 - Unit 10 Cryptographic primitives - Progress

HEAD at phase start: 9a82aa1
Stashed work: stash@{0} packages/crypto/hash.py draft (popped at session resume)

## Plan

- CP1.1 SHA-256 canonical hashing (hash.py + tests) - DONE
- CP1.2 Ed25519 sign/verify (sign.py + tests)
- CP1.3 Merkle chain (merkle.py + tests)
- CP1.4 Hypothesis property tests across all three
- CP1.5 Commit, push, green CI

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

## CP1.2 Ed25519 sign/verify - NEXT

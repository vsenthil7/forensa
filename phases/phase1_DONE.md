# Phase 1 - Unit 10 Cryptographic primitives - DONE

Status: COMPLETE
HEAD at completion: 165e3e4
CI at completion: SUCCESS on run 25806159982 (all 8 jobs green)

## Summary

All three crypto primitives shipped at 100% branch coverage, bound into a coherent canonical-JSON / sign / chain stack ready for Unit 11 Lobster Trap and Unit 13 Receipt issuance.

## Surface delivered

### packages/crypto/hash.py (CP1.1)

- canonical_json(payload) -> bytes  -- RFC 8785 JCS-lite (sort_keys + no whitespace + UTF-8)
- _normalise(value) -> Any  -- None raise, naive-datetime raise, tz-aware datetime ISO-8601, bytes base64-prefixed, set/frozenset sorted list, dict str-keys recurse, list/tuple recurse, str/int/float/bool passthrough, unsupported TypeError
- sha256_hex(payload) -> str  -- lowercase hex
- sha256_bytes(payload) -> bytes  -- 32-byte raw digest

30 stmts, 16 branches, 100% cov.

### packages/crypto/sign.py (CP1.2)

- generate_keypair() -> (private_key_bytes_32, public_key_bytes_32)
- sign(private_key_bytes, payload) -> 64-byte detached signature over canonical_json(payload)
- verify(public_key_bytes, payload, signature_bytes) -> bool  -- never raises; False on any failure (length, malformed key, bad signature)
- load_private_key(bytes) -> Ed25519PrivateKey  -- TypeError on non-bytes, ValueError on wrong length
- load_public_key(bytes) -> Ed25519PublicKey  -- TypeError on non-bytes, ValueError on wrong length

Bound to canonical_json so signing is over canonical bytes (key-order irrelevant). 100% cov.

### packages/crypto/merkle.py (CP1.3)

- entry_hash(entry) -> str  -- canonical SHA-256 hex over (sequence, payload_hash, prev_hash). Genesis None prev_hash bound as empty-string sentinel inside the function so canonical_json no-None rule holds.
- next_entry(prev_entry, payload_hash) -> dict  -- prev_entry=None is genesis
- verify_chain(entries) -> bool  -- sequence monotonicity + prev_hash linkage + entry_hash recompute. Empty list = valid.
- GENESIS_PREV_HASH = None, GENESIS_SEQUENCE = 0  -- public constants
- ChainError  -- ValueError subclass for malformed entries

100% cov.

## Tests

- tests/packages/test_crypto_hash.py:   25 collected (16 unit + 3 hypothesis property + 5 parametrised + 1 import) -- all green
- tests/packages/test_crypto_sign.py:   19 unit + 2 hypothesis property tests -- all green
- tests/packages/test_crypto_merkle.py: 22 collected (19 unit + 3 parametrised/property) -- all green

Total pytest 217 -> 282 (+65 tests).

Hypothesis property tests:
- canonical_json deterministic across repeated calls
- sha256_hex deterministic across repeated calls
- sha256_hex(p) == hexdigest(canonical_json(p)) for any valid payload
- sign-then-verify round-trip True for any canonicalisable payload
- verify rejects arbitrary random 64-byte blobs
- Any chain built sequentially via next_entry always verifies True
- Mutating any entry payload_hash in a chain of length 2-6 breaks verify_chain

## Phase 1 commits (oldest first)

- 4fd427e [FEAT] Unit 10 CP1.1: SHA-256 canonical hashing + 16 unit + 3 hypothesis tests
- bf788f3 [FIX]  Unit 10 CP1.1: ruff UP038 PEP-604 isinstance unions + import sort + UP012 + W292
- 264d221 [FIX]  Unit 10 CP1.1: ruff format (CI gate requires format --check passing)
- 34dc853 [DOC]  Phase 1 CP1.1 DONE: SHA-256 canonical hashing landed green on CI
- 9b450a1 [CHORE] .gitignore: exclude _backup/ (Claude FILE BACKUP RULE artefacts)
- b5d7b9d [FEAT] Unit 10 CP1.2: Ed25519 sign/verify + 19 unit + 2 hypothesis tests
- 7b85601 [FEAT] Unit 10 CP1.3: Merkle hash chain + 21 unit + 2 hypothesis tests
- c96947e [FIX]  Unit 10 CP1.3: bind empty-string sentinel for None prev_hash
- 165e3e4 [DOC]  Phase 1 CP1.2 + CP1.3 done: sign.py and merkle.py landed green on CI

## Lessons captured

- ruff UP038 PEP-604 isinstance unions require --unsafe-fixes; auto-fix is hidden by default but safe for primitive-type tuples
- CI runs both ruff check AND ruff format --check; local discipline must run both before push
- gh run watch hangs shell MCP at ~4min; poll with gh run view <id> --json status,conclusion in 60-90s sleeps
- shell:run_command on Windows: load via tool_search at session start; raw form returns null; powershell -Command wrapper required
- canonical_json(p) forbids None values (deliberate strict contract). Merkle genesis prev_hash IS None at the dict level; bind it as empty-string sentinel inside entry_hash() so callers still see entry['prev_hash'] is None but the canonical SHA-256 input stays non-None.
- Red-then-green commit shape works in hackathon mode: 7b85601 broken on CI -> c96947e fixed; git log reads as honest feat -> fix arc
- filesystem:edit_file can hang past 4 min and lock subsequent MCP calls. Recovery: restart Claude Desktop. For multi-anchor edits prefer the python-edit-script pattern or full-file rewrite via wrtb64.

## Next: Phase 2 - Unit 11 Lobster Trap policy verdict source

Build packages/policy/lobstertrap.py:
- PolicyVerdict schema + result types (allow/deny/escalate)
- LobsterTrapClient interface with retry/timeout
- MockLobsterTrapClient for tests + demo
- Policy bundle versioning + content_hash binding
- Commit + push + green CI

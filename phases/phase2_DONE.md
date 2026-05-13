# Phase 2 - Unit 11 Lobster Trap policy verdict source - DONE

Status: COMPLETE
HEAD at completion: 869f24f
CI at completion: SUCCESS on run 25820483912 (all gating jobs green; Docker build non-gating still completing)

## Summary

Lobster Trap policy verdict adapter + deterministic mock + tamper-evident PolicyBundle builder shipped at 100 pct branch coverage. The Trap is treated as an external service; Forensa captures evidences and replays its verdicts without making policy decisions itself. Mock implements the same async interface so the rest of Forensa never branches on real-vs-mock.

## Surface delivered

### packages/policy/lobstertrap.py (CP2.1-2.3)

- PolicyDecision: enum allow / deny / escalate
- LobsterTrapError(RuntimeError): terminal Trap failure
- PolicyVerdict (frozen dataclass): decision + policy_bundle_id + policy_bundle_version + content_hash + reason + evaluated_at; rejects bad decision type, naive datetime, malformed hash, empty reason
- LobsterTrapClient (ABC): async evaluate(tenant_id, action) -> PolicyVerdict
- MockLobsterTrapClient: deterministic in-memory mock; rule-driven (deny_kind / escalate_kind / else allow); custom content -> different content_hash; optional latency_ms

63 stmts, 18 branches, 100 pct cov.

### packages/policy/bundle_builder.py (CP2.4)

- compute_content_hash(content) -> SHA-256 hex of canonical_json(content)
- build_bundle(tenant_id, version, content) -> PolicyBundle  (two-step build: draft to let pydantic coerce, then rebind hash over post-validated content; guarantees verify_content_hash returns True regardless of schema-level string coercions)
- rebind_bundle(bundle, new_content, new_version) -> NEW PolicyBundle
- verify_content_hash(bundle) -> bool
- require_content_hash(bundle): raises PolicyBundleHashMismatchError
- PolicyBundleHashMismatchError(ValueError)
- bump_major / bump_minor / bump_patch  (pure dotted-decimal version helpers)

44 stmts, 10 branches, 100 pct cov.

## Tests

- tests/packages/test_lobstertrap.py: 23 unit + 2 hypothesis property tests
- tests/packages/test_bundle_builder.py: 22 unit + 2 hypothesis property tests

Total pytest 282 -> 327 (+45 tests).

Hypothesis property tests:
- MockLobsterTrapClient: decision is deterministic per kind across instances
- MockLobsterTrapClient: every verdict carries configured policy_bundle_id and version
- build_bundle: content_hash matches sha256_hex(post-validated content) for any canonicalisable content
- bump_patch: only increments the third component

## Phase 2 commits

- 3430997 [FEAT] Unit 11 CP2.1-2.3: Lobster Trap policy verdict adapter + 23 unit + 2 hypothesis tests
- c8ddb5f [FIX]  Unit 11 CP2.3: use new_event_loop+close instead of asyncio.run (Linux py3.12 unraisable-exception warnings under hypothesis)
- 869f24f [FEAT] Unit 11 CP2.4: PolicyBundle builder with content_hash binding + version bumpers + 22 unit + 2 hypothesis tests

## Lessons captured

- Pydantic v2 str_strip_whitespace=True coerces dict KEYS too, not just string fields. Bind content_hash AFTER pydantic validation, not before, otherwise verify_content_hash will fail on inputs whose keys contain whitespace. Two-step build pattern: draft to coerce, then rebind hash over draft.content.
- asyncio.run() inside repeated test calls under hypothesis on Linux py3.12 triggers unraisable-exception warnings (socket FDs surviving past loop teardown). pyproject filterwarnings=["error"] turns these into test failures on CI. Fix: explicit new_event_loop()/close() helper.
- Unreachable defensive-coding branches cost 100 pct coverage. Remove them or add # pragma: no cover. Honest code wins (remove).
- N818 ruff: exception classes must end in Error suffix. PolicyBundleHashMismatch -> PolicyBundleHashMismatchError.
- shell:run_command Start-Sleep cap is around 120 seconds before MCP wrapper times out at 4 min. Multiple short polls > one long sleep.
- tools/wrtb64_from_file.py is now the right helper for source files > 5KB; write b64 to a temp file via chunked Add-Content, then python tools/wrtb64_from_file.py target.py b64tmp.

## Next: Phase 3 - Unit 12 Policy snapshot binding (BR-04)

Goal: every Event-to-Receipt records the exact policy_bundle.content_hash active at ingest.
Checkpoints:
- CP3.1 Policy snapshot capture at event ingest
- CP3.2 Receipt-to-PolicyBundle FK binding enforced
- CP3.3 Replay-time policy resolution (snapshot, not current)
- CP3.4 Commit + push + green CI

Files to read first: packages/schema/event.py, packages/schema/receipt.py, apps/api/routes/events.py.

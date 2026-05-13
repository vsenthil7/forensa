# Phase 2 - Unit 11 Lobster Trap policy verdict source - Progress

HEAD at phase start: 7a37998

## Plan

- CP2.1 PolicyVerdict schema + result types (allow/deny/escalate) - DONE
- CP2.2 LobsterTrapClient interface with retry/timeout - DONE (interface only; HTTP impl deferred to post-hackathon)
- CP2.3 MockLobsterTrapClient for tests + demo - DONE
- CP2.4 Policy bundle versioning + content_hash binding - DONE
- CP2.5 Commit + push + green CI - DONE

## Phase 2 closing state

HEAD: 869f24f
CI run: 25820483912 - SUCCESS (all gating jobs green; Docker build non-gating)
327 pytest passed (was 282 + 45 new across CP2.1-2.4)
100 pct coverage maintained on all measured modules

## CP2.1-2.3 Lobster Trap adapter + Mock - DONE

Commits:
- 3430997 [FEAT] Unit 11 CP2.1-2.3: Lobster Trap policy verdict adapter (PolicyDecision + PolicyVerdict + abstract client + Mock) + 23 unit + 2 hypothesis tests
- c8ddb5f [FIX] Unit 11 CP2.3: use new_event_loop+close instead of asyncio.run to silence Linux py3.12 unraisable-exception warnings under hypothesis

Surface:
- PolicyDecision enum: allow / deny / escalate
- PolicyVerdict frozen dataclass with decision + policy_bundle_id + policy_bundle_version + content_hash + reason + evaluated_at; rejects non-enum decision, naive datetime, malformed hash, empty reason
- LobsterTrapError(RuntimeError) for terminal Trap failures
- LobsterTrapClient ABC with async evaluate(tenant_id, action) -> PolicyVerdict
- MockLobsterTrapClient: keyed on action["kind"]; deny_kind -> DENY, escalate_kind -> ESCALATE, else ALLOW; bound to a fixed mock policy bundle so content_hash is deterministic; optional latency_ms

Tests: 23 unit (including 4 PolicyDecision/Verdict, 8 Mock paths, 5 validation) + 2 hypothesis property tests.

## CP2.4 PolicyBundle builder - DONE

Commit:
- 869f24f [FEAT] Unit 11 CP2.4: PolicyBundle builder with content_hash binding + version bumpers + 22 unit + 2 hypothesis tests

Surface (packages/policy/bundle_builder.py):
- compute_content_hash(content) -> sha256_hex (canonical)
- build_bundle(tenant_id, version, content) -> PolicyBundle  (two-step pattern: builds draft to let pydantic str_strip_whitespace coerce, then rebinds hash over post-validated content)
- rebind_bundle(bundle, new_content, new_version) -> NEW PolicyBundle  (immutable update; same two-step pattern)
- verify_content_hash(bundle) -> bool
- require_content_hash(bundle)  (raises PolicyBundleHashMismatchError)
- PolicyBundleHashMismatchError(ValueError)
- bump_major / bump_minor / bump_patch (dotted-decimal pure functions)

Tests: 22 unit + 2 hypothesis property tests (content_hash binding round-trip, bump_patch semantics).

## Lessons captured

- Pydantic v2 str_strip_whitespace=True coerces dict KEYS too, not just string fields. If you bind content_hash before construction and the content has whitespace-only keys, verify_content_hash will fail because the stored content differs from the hashed content. Fix: build a draft bundle first to let pydantic coerce, then rebind the hash over draft.content.
- Hypothesis with @given on tests that drive asyncio.run() repeatedly under Linux py3.12 triggers unraisable-exception warnings (socket FDs surviving past loop teardown). pyproject filterwarnings=["error"] turns these into failures. Fix: explicit new_event_loop()/close() helper.
- Unreachable defensive-coding branches (e.g. if len(parts) < 1 after a _parse_version that already rejects empty strings) cost 100 pct coverage. Either remove them or add # pragma: no cover. We chose remove (honest code).
- N818 ruff rule requires exception classes to end with Error suffix. PolicyBundleHashMismatch -> PolicyBundleHashMismatchError.
- shell:run_command Start-Sleep cap is around 120 seconds before MCP wrapper timeout at 4 min. Use multiple short polls rather than one long sleep.

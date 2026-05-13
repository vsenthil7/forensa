# Forensa Build - Master Plan

HEAD at plan creation: 06f369b
Hackathon deadline: Mon 19/05/2026
Wed 14/05 EoD = pivot trigger to AegisOne if blocking risk.

## Hard rules

- Git first then test. Commit before testing where it makes sense, never test without committing.
- 100% coverage gate on Python AND TypeScript AND Playwright. No scope shrink.
- Playwright counts. E2E must execute and pass; not skipped.
- No date/time ritual prose. No 29-minute stamps.
- One progress document per phase under phases/PHASE-progress.md updated after each CP.

## Phases

### Phase 0 - Green CI
Goal: ci-gate passes across all 7 jobs.
Acceptance: gh run list --limit 1 shows success on a push.
Checkpoints:
- CP0.1: Diagnose & fix Playwright Wait for API ready timeout
- CP0.2: Verify all 7 CI jobs green
- CP0.3: Commit + push, watch CI

### Phase 1 - Unit 10: Cryptographic primitives
Goal: packages/crypto/{hash,sign,merkle}.py with hypothesis property tests, 100pct cov.
Acceptance: 217 + crypto tests all pass; 100pct cov maintained; ci-gate green.
Checkpoints:
- CP1.1: SHA-256 canonical hashing (JSON-stable, deterministic)
- CP1.2: Ed25519 sign/verify with key serialization
- CP1.3: Merkle chain (prev_hash binding, append-only, audit traversal)
- CP1.4: hypothesis property tests for all three
- CP1.5: Commit + push + green CI


### Phase 2 - Unit 11: Lobster Trap policy verdict source
Goal: packages/policy/lobstertrap.py with mock verdict source, MCP-shaped interface.
Checkpoints:
- CP2.1: PolicyVerdict schema + result types (allow/deny/escalate)
- CP2.2: LobsterTrapClient interface with retry/timeout
- CP2.3: MockLobsterTrapClient for tests + demo
- CP2.4: Policy bundle versioning + content_hash binding
- CP2.5: Commit + push + green CI

### Phase 3 - Unit 12: Policy snapshot binding (BR-04)
Goal: Every Event-to-Receipt records the exact policy_bundle.content_hash active at ingest.
Checkpoints:
- CP3.1: Policy snapshot capture at event ingest
- CP3.2: Receipt-to-PolicyBundle FK binding enforced
- CP3.3: Replay-time policy resolution (snapshot, not current)
- CP3.4: Commit + push + green CI


### Phase 4 - Unit 13: Receipt issuance pipeline
Goal: POST /v1/events writes Event + PolicySnapshot + Receipt as one atomic txn.
Checkpoints:
- CP4.1: Receipt builder (sequence, prev_hash, payload_hash, signature)
- CP4.2: Atomic write across Event + Receipt
- CP4.3: Sequence monotonicity invariant per tenant
- CP4.4: Hash chain integrity tests
- CP4.5: Commit + push + green CI

### Phase 5 - Unit 14: Console health + receipt views
Goal: Operator console shows live API health + recent receipts table.
Checkpoints:
- CP5.1: HealthBadge done; extend to status pill
- CP5.2: Receipts list page calling /v1/receipts
- CP5.3: Receipt detail page with hash chain visualisation
- CP5.4: Playwright tests for each view, 100pct cov
- CP5.5: Commit + push + green CI


### Phase 6 - Unit 15: Evidence pack export
Goal: Compliance officer exports tamper-evident bundle (JSON-LD + PROV-O + PDF).
Checkpoints:
- CP6.1: JSON-LD evidence schema
- CP6.2: PROV-O lineage block
- CP6.3: PDF rendering with hash chain + signatures
- CP6.4: Export endpoint + Playwright E2E
- CP6.5: Commit + push + green CI

### Phase 7 - Unit 16: Gemini Pro narrative generation
Goal: Compliance officer queries past incident; Gemini Pro renders regulator narrative.
Checkpoints:
- CP7.1: Gemini client wrapper
- CP7.2: Narrative prompt template + counterfactual reasoning
- CP7.3: Narrative-to-evidence-pack integration
- CP7.4: Commit + push + green CI

### Phase 8 - Unit 17: Demo tabletop + load test
Goal: Live demo walk-through script + BR-09 throughput load test (1k events/s).
Checkpoints:
- CP8.1: Tabletop scenario script (incident replay)
- CP8.2: Omniverse physical-action replay cameo (stretch)
- CP8.3: Load test passes BR-09
- CP8.4: Commit + push + green CI

## Progress format

For each CP done, append to phases/PHASE-progress.md.
At end of each phase, summarise in phases/PHASE-DONE.md.
After all phases, consolidate to phases/FORENSA_COMPLETE.md.


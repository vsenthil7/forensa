# Phase 3 - Unit 12 Policy snapshot binding (BR-04) - DONE

Status: COMPLETE
HEAD at completion: dabac3a
CI at completion: SUCCESS on run 25823589017 (all 7 gating jobs green; Docker build non-gating still completing)

## Summary

BR-04 implementation complete. Every Event-to-Receipt now records the exact policy_bundle.content_hash that was active at ingest, captured into a PolicySnapshot persisted in the policy_snapshots table and linked from receipts.policy_snapshot_id. Replay-time resolution binds to the snapshot, never the live bundle, with drift detection as a diagnostic.

## Surface delivered

### packages/policy/snapshot.py (CP3.1)

- PolicySnapshot frozen dataclass: 6 fields with validation
- capture_snapshot(bundle, verdict): triple-check binding (id match, hash match, bundle self-consistent)
- resolve_snapshot / snapshot_matches_bundle: drift detection raising and non-raising
- PolicySnapshotDriftError

### packages/ledger/models.py + alembic 0002 (CP3.2)

- PolicySnapshotRow ORM mapping for policy_snapshots table
- ReceiptRow.policy_snapshot_id FK + index
- alembic migration 0002_policy_snapshot adds the table, the column, the FK, three indexes, and a CHECK constraint on verdict_decision

### packages/policy/replay.py (CP3.3)

- ReplayPolicy frozen dataclass with drift_detected flag
- resolve_replay_policy: binds to snapshot.content_hash, NEVER to live_bundle.content_hash
- ReplayResolutionError

## Tests

- tests/packages/test_snapshot.py: 16 unit + 1 hypothesis property
- tests/packages/test_ledger_models.py: 13 tests (was 12; added test_policy_snapshot_columns_constraints_indexes)
- tests/packages/test_alembic_migration.py: 31 tests (parametrised; was 22 + 9 new for the new table/indexes/constraints)
- tests/packages/test_replay.py: 5 unit tests

Total pytest 327 -> 358 (+31 tests).

## Phase 3 commits

- 1a151f4 [FEAT] Unit 12 CP3.1: PolicySnapshot for BR-04 ingest-time bind + 16 unit + 1 hypothesis tests
- c3dcd36 [FEAT] Unit 12 CP3.2: PolicySnapshotRow ORM + alembic 0002 migration + receipts.policy_snapshot_id FK
- dabac3a [FEAT] Unit 12 CP3.3: replay-time policy resolution (binds to snapshot.content_hash never live bundle; drift_detected flag) + 5 unit tests

## Lessons captured

- PolicyBundle.content_hash validator enforces hex [0-9a-f] only. Test fixtures must use valid hex characters (a-f and 0-9) for arbitrary-but-different hashes.
- BR-04 design: snapshot is the source of truth at replay time. resolve_replay_policy refuses to read live_bundle.content_hash even when there is no drift. Live bundle only contributes to the drift_detected boolean.
- Two-step ledger ORM edit pattern: add the new ORM class first, then add the dependent FK column. Doing both in one edit_file call risks the FK landing in the wrong class because old_str patterns can match in multiple places.

## Session window 4 + 5 stamps

SESSION (window 4) START: 2026-05-13 20:03:40
SESSION (window 4) END:   2026-05-13 20:53:45 (ceiling breached by ~20 min)
SESSION (window 5) START: 2026-05-13 20:55:23
TASK START CP3.2:        2026-05-13 20:56:14
TASK END CP3.2:          2026-05-13 21:00:21
TASK START CP3.3:        2026-05-13 21:00:59
TASK END CP3.3:          2026-05-13 21:10:12
TASK START Phase3 close: 2026-05-13 21:16:26

## Next: Phase 4 - Unit 13 Receipt issuance pipeline

Goal: POST /v1/events writes Event + PolicySnapshot + Receipt as one atomic transaction.
Checkpoints:
- CP4.1 Receipt builder (sequence, prev_hash, payload_hash, signature)
- CP4.2 Atomic write across Event + Receipt
- CP4.3 Sequence monotonicity invariant per tenant
- CP4.4 Hash chain integrity tests
- CP4.5 Commit + push + green CI

Files to read first: apps/api/routes/events.py, packages/ledger/models.py (existing), packages/schema/receipt.py.

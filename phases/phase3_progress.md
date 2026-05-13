# Phase 3 - Unit 12 Policy snapshot binding (BR-04) - Progress

HEAD at phase start: a006be1

## Plan

- CP3.1 Policy snapshot capture at event ingest - DONE (1a151f4, CI 25821721865)
- CP3.2 Receipt-to-PolicyBundle FK binding enforced - DONE (c3dcd36, CI 25823146494)
- CP3.3 Replay-time policy resolution (snapshot not current) - DONE (dabac3a, CI 25823589017)
- CP3.4 Commit + push + green CI - DONE

## Phase 3 closing state

HEAD: dabac3a
CI run: 25823589017 - all gating jobs SUCCESS (Docker build non-gating still completing)
358 pytest passed (was 327 + 31 new across CP3.1-3.3)
100 pct coverage maintained on all measured modules

## CP3.1 PolicySnapshot - DONE

Commit: 1a151f4 [FEAT] Unit 12 CP3.1: PolicySnapshot for BR-04 ingest-time bind

Surface (packages/policy/snapshot.py):
- PolicySnapshot frozen dataclass: policy_bundle_id + version + content_hash + captured_at + verdict_decision + verdict_reason; rejects naive datetime, malformed hash, empty version/decision/reason
- capture_snapshot(bundle, verdict): bundle/verdict must agree on id and content_hash; refuses to capture over a tampered bundle
- resolve_snapshot(snapshot, live_bundle): raises PolicySnapshotDriftError on id mismatch or content drift
- snapshot_matches_bundle(snapshot, bundle) -> bool (non-raising variant)
- PolicySnapshotDriftError(RuntimeError)

Tests: 16 unit + 1 hypothesis property test (decision/reason preservation across allow/deny/escalate).

## CP3.2 Ledger persistence - DONE

Commit: c3dcd36 [FEAT] Unit 12 CP3.2: PolicySnapshotRow ORM + alembic 0002 migration + receipts.policy_snapshot_id FK

Surface:
- packages/ledger/models.py: new PolicySnapshotRow class (table policy_snapshots) with 8 columns, 2 FKs (tenant, policy_bundle), 3 indexes, CK on verdict_decision IN (allow, deny, escalate)
- ReceiptRow.policy_snapshot_id column + FK to policy_snapshots.id with ondelete RESTRICT
- alembic/versions/20260513_2055_policy_snapshot.py: revision 0002_policy_snapshot, depends on 0001_initial; creates policy_snapshots table and adds receipts.policy_snapshot_id column + FK + index

Tests: existing test_ledger_models.py + test_alembic_migration.py extended to assert new table, columns, FKs, indexes, constraints. 6 tables total (was 5). 12 indexes total (was 8).

## CP3.3 Replay-time resolution - DONE

Commit: dabac3a [FEAT] Unit 12 CP3.3: replay-time policy resolution

Surface (packages/policy/replay.py):
- ReplayPolicy frozen dataclass: policy_bundle_id + version + content_hash + verdict_decision + verdict_reason + drift_detected
- resolve_replay_policy(receipt_policy_bundle_id, receipt_policy_snapshot_id, snapshot, live_bundle): NEVER returns live bundle content_hash; always returns snapshot.content_hash; flags drift_detected when live bundle differs
- ReplayResolutionError(RuntimeError): raised when snapshot does not belong to the receipt

Tests: 5 unit tests covering happy path, drift detection (same id + different hash), missing-live-bundle forensic allowance, snapshot-bundle-id mismatch error.

## Lessons captured this phase

- PolicyBundle.content_hash validator enforces hex chars [0-9a-f] only. Test fixtures using 'z' * 64 fail at construction; use 'f' * 64 (valid hex) or any digit char for arbitrary-but-different hashes.
- BR-04 implementation: the snapshot IS the source of truth at replay time. resolve_replay_policy refuses to read live_bundle.content_hash into the ReplayPolicy even when there is no drift. Live bundle only matters for the boolean drift_detected flag.
- Two-step ledger ORM edit pattern: add the new class first then add the FK column to the dependent table. Doing both in one edit_file call caused the FK to be inserted into the wrong class because the old_str matched in two places. Fixed by undoing the misplaced edit and redoing with anchor-disambiguated old_str.

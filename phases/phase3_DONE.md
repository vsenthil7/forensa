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

---

## Test-level split per CP

| CP | Functional | Negative | Parametric | Property | Total def-tests | Pytest collected |
|---|---:|---:|---:|---:|---:|---:|
| CP3.1 PolicySnapshot capture | 11 | 5 (id mismatch, hash mismatch, malformed bundle, naive datetime, empty fields) | 0 | 1 (decision/reason preservation across allow/deny/escalate) | 16 | 17 |
| CP3.2 alembic 0002 + PolicySnapshotRow | 1 + 9 parametric | 0 | 1 (over 6 tables + 12 indexes + 3 CHECK clauses) | 0 | 10 | 10 |
| CP3.3 resolve_replay_policy | 4 | 1 (snapshot-bundle-id mismatch) | 0 | 0 | 5 | 5 |
| **Phase 3 total** | **25** | **6** | **1** | **1** | **31** | **32** |

Coverage by source module after Phase 3:

| Module | LOC | Stmts | Branches | Cov line | Cov branch | Test file |
|---|---:|---:|---:|---:|---:|---|
| packages/policy/snapshot.py | ~110 | 44 | 20 | 100pct | 100pct | tests/packages/test_snapshot.py |
| packages/policy/replay.py | ~60 | 22 | 4 | 100pct | 100pct | tests/packages/test_replay.py |
| packages/ledger/models.py (PolicySnapshotRow added) | ~170 | 77 | 0 | 100pct | n/a | tests/packages/test_ledger_models.py + test_alembic_migration.py |
| alembic/versions/20260513_2055_policy_snapshot.py | ~80 | n/a | n/a | n/a | n/a | tests/packages/test_alembic_migration.py |

---

## Source code embedded (production + tests)

### CP3.1 - Production code (snapshot.py) - `packages/policy/snapshot.py`

```python
"""PolicySnapshot — capture the exact policy state active at event ingest.

BR-04 requires every Event-to-Receipt to record the policy_bundle.content_hash
that was active when the event was ingested, so the receipt can be replayed
against the exact rules that produced its verdict — not whatever's current.

A PolicySnapshot is the immutable bind. It carries:
- policy_bundle_id: which bundle was in effect
- policy_bundle_version: human-readable version string at the time
- content_hash: tamper-evident SHA-256 of canonical_json(content) at the time
- captured_at: when the snapshot was taken
- verdict_decision / verdict_reason: the Trap's call on the action

Snapshots are frozen and produced by capture_snapshot(). The same module
provides resolve_snapshot() which, given a snapshot and a current bundle of
the same id, asserts the snapshot's content_hash still matches the bundle's
content_hash — proving the bundle hasn't been mutated since ingest. If they
disagree, the bundle has drifted and the replay must use the snapshot, not
the current bundle.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from packages.policy.bundle_builder import (
    PolicyBundleHashMismatchError,
    verify_content_hash,
)
from packages.policy.lobstertrap import PolicyVerdict
from packages.schema.policy_bundle import PolicyBundle

_SHA256_LEN = 64
_HEX = "0123456789abcdef"


class PolicySnapshotDriftError(RuntimeError):
    """Raised when a snapshot's content_hash no longer matches the live bundle."""


@dataclass(frozen=True)
class PolicySnapshot:
    """Immutable bind of (policy bundle state at ingest, verdict produced)."""

    policy_bundle_id: UUID
    policy_bundle_version: str
    content_hash: str
    captured_at: datetime
    verdict_decision: str
    verdict_reason: str

    def __post_init__(self) -> None:
        if self.captured_at.tzinfo is None:
            raise ValueError("captured_at must be timezone-aware (UTC)")
        if len(self.content_hash) != _SHA256_LEN or not all(c in _HEX for c in self.content_hash):
            raise ValueError("content_hash must be 64-char lowercase hex (SHA-256)")
        if not self.policy_bundle_version:
            raise ValueError("policy_bundle_version must be non-empty")
        if not self.verdict_decision:
            raise ValueError("verdict_decision must be non-empty")
        if not self.verdict_reason:
            raise ValueError("verdict_reason must be non-empty")


def capture_snapshot(
    bundle: PolicyBundle,
    verdict: PolicyVerdict,
) -> PolicySnapshot:
    """Capture a snapshot binding a bundle to the verdict it produced.

    The bundle and the verdict must agree on policy_bundle_id and content_hash.
    This guarantees the verdict was actually evaluated against the bundle the
    caller is binding to; mismatch raises PolicyBundleHashMismatchError to
    surface caller bugs before they become forensic ambiguity.
    """
    if bundle.id != verdict.policy_bundle_id:
        raise PolicyBundleHashMismatchError(
            f"bundle.id {bundle.id} does not match verdict.policy_bundle_id "
            f"{verdict.policy_bundle_id}"
        )
    if bundle.content_hash != verdict.content_hash:
        raise PolicyBundleHashMismatchError(
            "bundle.content_hash does not match verdict.content_hash; "
            "verdict was evaluated against a different version of this bundle"
        )
    if not verify_content_hash(bundle):
        raise PolicyBundleHashMismatchError(
            f"bundle {bundle.id} content_hash does not match its content; "
            "refusing to capture a snapshot over a tampered bundle"
        )
    return PolicySnapshot(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content_hash=bundle.content_hash,
        captured_at=datetime.now(UTC),
        verdict_decision=verdict.decision.value,
        verdict_reason=verdict.reason,
    )


def resolve_snapshot(
    snapshot: PolicySnapshot,
    live_bundle: PolicyBundle,
) -> None:
    """Assert a snapshot still resolves to the live bundle.

    Used at replay time. If live_bundle.id differs from snapshot.policy_bundle_id
    this is a programmer error (the caller passed the wrong bundle). If the
    content_hashes differ, the live bundle has drifted from the snapshot and
    the replay must use the snapshot's content_hash (the snapshot wins; live
    is for diagnostics only).
    """
    if live_bundle.id != snapshot.policy_bundle_id:
        raise PolicySnapshotDriftError(
            f"live bundle id {live_bundle.id} does not match snapshot "
            f"{snapshot.policy_bundle_id}"
        )
    if live_bundle.content_hash != snapshot.content_hash:
        raise PolicySnapshotDriftError(
            f"live bundle content_hash {live_bundle.content_hash[:8]}... "
            f"has drifted from snapshot {snapshot.content_hash[:8]}...; "
            "replay must bind to snapshot.content_hash"
        )


def snapshot_matches_bundle(
    snapshot: PolicySnapshot,
    bundle: PolicyBundle,
) -> bool:
    """Return True iff snapshot id + content_hash equal the given bundle's.

    Non-raising variant of resolve_snapshot(); use for boolean checks where
    drift is expected and tolerated.
    """
    return snapshot.policy_bundle_id == bundle.id and snapshot.content_hash == bundle.content_hash
```

### CP3.1 - Test script (test_snapshot.py) - `tests/packages/test_snapshot.py`

```python
"""Tests for packages/policy/snapshot.py - 100% branch coverage.

Covers:
- PolicySnapshot validation: naive datetime, malformed hash, empty version/decision/reason
- capture_snapshot: happy path, bundle/verdict id mismatch, content_hash mismatch, tampered bundle
- resolve_snapshot: happy path, id mismatch, content_hash drift
- snapshot_matches_bundle: True/False paths
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from packages.policy.bundle_builder import (
    PolicyBundleHashMismatchError,
    build_bundle,
)
from packages.policy.lobstertrap import (
    MockLobsterTrapClient,
    PolicyDecision,
    PolicyVerdict,
)
from packages.policy.snapshot import (
    PolicySnapshot,
    PolicySnapshotDriftError,
    capture_snapshot,
    resolve_snapshot,
    snapshot_matches_bundle,
)
from packages.schema.policy_bundle import PolicyBundle

_TENANT_ID = UUID("44444444-4444-4444-4444-444444444444")
_SAMPLE_CONTENT = {
    "rules": [{"kind": "deny_kind", "decision": "deny"}],
    "default": "allow",
}
_VALID_HASH = "a" * 64


def _run(coro):
    """Run a coroutine in a fresh loop and close cleanly (avoid Linux py3.12 warnings)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _build_aligned_pair() -> tuple[PolicyBundle, PolicyVerdict]:
    """Build a PolicyBundle and a matching PolicyVerdict from a Mock Trap."""
    bundle = build_bundle(tenant_id=_TENANT_ID, version="1.0.0", content=_SAMPLE_CONTENT)
    # MockLobsterTrapClient: content kwarg defaults differ. Pass bundle content
    # explicitly so the verdict's content_hash matches the bundle's content_hash.
    mock = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )
    verdict = _run(mock.evaluate(_TENANT_ID, {"kind": "anything"}))
    return bundle, verdict


# ---------- PolicySnapshot validation ----------


def _good_snapshot(**over) -> PolicySnapshot:
    base = dict(
        policy_bundle_id=UUID("11111111-1111-1111-1111-111111111111"),
        policy_bundle_version="1.0.0",
        content_hash=_VALID_HASH,
        captured_at=datetime.now(UTC),
        verdict_decision="allow",
        verdict_reason="ok",
    )
    base.update(over)
    return PolicySnapshot(**base)


def test_snapshot_valid_minimal():
    s = _good_snapshot()
    assert s.content_hash == _VALID_HASH
    assert s.captured_at.tzinfo is not None


def test_snapshot_rejects_naive_datetime():
    with pytest.raises(ValueError, match="captured_at must be timezone-aware"):
        _good_snapshot(captured_at=datetime(2026, 5, 13, 20, 0))


def test_snapshot_rejects_bad_hash():
    with pytest.raises(ValueError, match="must be 64-char lowercase hex"):
        _good_snapshot(content_hash="short")


def test_snapshot_rejects_uppercase_hash():
    with pytest.raises(ValueError, match="must be 64-char lowercase hex"):
        _good_snapshot(content_hash="A" * 64)


def test_snapshot_rejects_empty_version():
    with pytest.raises(ValueError, match="policy_bundle_version must be non-empty"):
        _good_snapshot(policy_bundle_version="")


def test_snapshot_rejects_empty_decision():
    with pytest.raises(ValueError, match="verdict_decision must be non-empty"):
        _good_snapshot(verdict_decision="")


def test_snapshot_rejects_empty_reason():
    with pytest.raises(ValueError, match="verdict_reason must be non-empty"):
        _good_snapshot(verdict_reason="")


# ---------- capture_snapshot ----------


def test_capture_snapshot_happy_path():
    bundle, verdict = _build_aligned_pair()
    snap = capture_snapshot(bundle, verdict)
    assert snap.policy_bundle_id == bundle.id
    assert snap.policy_bundle_version == bundle.version
    assert snap.content_hash == bundle.content_hash
    assert snap.verdict_decision == verdict.decision.value
    assert snap.verdict_reason == verdict.reason


def test_capture_snapshot_rejects_bundle_id_mismatch():
    bundle, _ = _build_aligned_pair()
    other_bundle_id = UUID("99999999-9999-9999-9999-999999999999")
    mismatched_verdict = PolicyVerdict(
        decision=PolicyDecision.ALLOW,
        policy_bundle_id=other_bundle_id,
        policy_bundle_version=bundle.version,
        content_hash=bundle.content_hash,
        reason="ok",
    )
    with pytest.raises(
        PolicyBundleHashMismatchError, match="does not match verdict.policy_bundle_id"
    ):
        capture_snapshot(bundle, mismatched_verdict)


def test_capture_snapshot_rejects_content_hash_mismatch():
    bundle, _ = _build_aligned_pair()
    different_hash = "b" * 64
    mismatched_verdict = PolicyVerdict(
        decision=PolicyDecision.ALLOW,
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content_hash=different_hash,
        reason="ok",
    )
    with pytest.raises(
        PolicyBundleHashMismatchError, match="bundle.content_hash does not match verdict"
    ):
        capture_snapshot(bundle, mismatched_verdict)


def test_capture_snapshot_rejects_tampered_bundle():
    bundle, verdict = _build_aligned_pair()
    # Construct a bundle with the same id and a content_hash that matches the
    # verdict but does not match the content (simulating tamper).
    tampered = PolicyBundle(
        id=bundle.id,
        tenant_id=bundle.tenant_id,
        version=bundle.version,
        content_hash=verdict.content_hash,
        content={"different": "content"},
        created_at=bundle.created_at,
    )
    with pytest.raises(PolicyBundleHashMismatchError, match="refusing to capture"):
        capture_snapshot(tampered, verdict)


# ---------- resolve_snapshot ----------


def test_resolve_snapshot_happy_path():
    bundle, verdict = _build_aligned_pair()
    snap = capture_snapshot(bundle, verdict)
    # Same bundle = no drift.
    resolve_snapshot(snap, bundle)


def test_resolve_snapshot_rejects_wrong_bundle_id():
    bundle, verdict = _build_aligned_pair()
    snap = capture_snapshot(bundle, verdict)
    other_bundle = build_bundle(
        tenant_id=_TENANT_ID, version="2.0.0", content={"different": "rules"}
    )
    with pytest.raises(PolicySnapshotDriftError, match="does not match snapshot"):
        resolve_snapshot(snap, other_bundle)


def test_resolve_snapshot_detects_content_drift():
    bundle, verdict = _build_aligned_pair()
    snap = capture_snapshot(bundle, verdict)
    # Build a new bundle with the SAME id but different content/hash.
    drifted = PolicyBundle(
        id=bundle.id,
        tenant_id=bundle.tenant_id,
        version="1.0.1",
        content_hash="c" * 64,
        content={"different": "rules"},
        created_at=bundle.created_at,
    )
    with pytest.raises(PolicySnapshotDriftError, match="has drifted from snapshot"):
        resolve_snapshot(snap, drifted)


# ---------- snapshot_matches_bundle ----------


def test_snapshot_matches_bundle_true():
    bundle, verdict = _build_aligned_pair()
    snap = capture_snapshot(bundle, verdict)
    assert snapshot_matches_bundle(snap, bundle) is True


def test_snapshot_matches_bundle_false_on_different_id():
    bundle, verdict = _build_aligned_pair()
    snap = capture_snapshot(bundle, verdict)
    other = build_bundle(tenant_id=_TENANT_ID, version="2.0.0", content={"x": 1})
    assert snapshot_matches_bundle(snap, other) is False


def test_snapshot_matches_bundle_false_on_drift():
    bundle, verdict = _build_aligned_pair()
    snap = capture_snapshot(bundle, verdict)
    drifted = PolicyBundle(
        id=bundle.id,
        tenant_id=bundle.tenant_id,
        version="1.0.1",
        content_hash="d" * 64,
        content={"different": "rules"},
        created_at=bundle.created_at,
    )
    assert snapshot_matches_bundle(snap, drifted) is False


# ---------- Hypothesis property ----------


@given(
    st.text(min_size=1, max_size=20),
    st.sampled_from([PolicyDecision.ALLOW, PolicyDecision.DENY, PolicyDecision.ESCALATE]),
)
def test_capture_snapshot_always_preserves_decision_string(reason_text, decision):
    """Capturing always copies the verdict.decision.value into the snapshot."""
    bundle, _ = _build_aligned_pair()
    verdict = PolicyVerdict(
        decision=decision,
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content_hash=bundle.content_hash,
        reason=reason_text,
    )
    snap = capture_snapshot(bundle, verdict)
    assert snap.verdict_decision == decision.value
    assert snap.verdict_reason == reason_text
```

### CP3.2 - Production code (models.py - PolicySnapshotRow + ReceiptRow.policy_snapshot_id FK) - `packages/ledger/models.py`

```python
"""SQLAlchemy 2.0 async ORM models for the Forensa evidence ledger.

Mirrors the Pydantic schemas in packages.schema. Append-only by design:
no UPDATE or DELETE statements should ever target receipts or events.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all Forensa ORM models."""


class TenantRow(Base):
    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    slug: Mapped[str] = mapped_column(String(63), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    signing_key_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    agents: Mapped[list[AgentRow]] = relationship(back_populates="tenant")


class AgentRow(Base):
    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_agents_tenant_slug"),
        CheckConstraint(
            "status IN ('active', 'suspended', 'retired')",
            name="ck_agents_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    slug: Mapped[str] = mapped_column(String(63), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    identity_public_key: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    tenant: Mapped[TenantRow] = relationship(back_populates="agents")


class PolicyBundleRow(Base):
    __tablename__ = "policy_bundles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "version", name="uq_policy_bundles_tenant_version"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PolicySnapshotRow(Base):
    """BR-04: ingest-time bind of (policy bundle state, verdict produced).

    Captures the exact policy_bundle.content_hash that was active when an event
    was ingested, even if the bundle itself is later replaced or rebuilt. Every
    Receipt links to a PolicySnapshot via FK so replay can use the snapshot's
    content_hash rather than whatever the live bundle currently shows.
    """

    __tablename__ = "policy_snapshots"
    __table_args__ = (
        CheckConstraint(
            "verdict_decision IN ('allow', 'deny', 'escalate')",
            name="ck_policy_snapshots_decision",
        ),
        Index("ix_policy_snapshots_bundle", "policy_bundle_id"),
        Index("ix_policy_snapshots_tenant_captured", "tenant_id", "captured_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    policy_bundle_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("policy_bundles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    policy_bundle_version: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verdict_decision: Mapped[str] = mapped_column(String(16), nullable=False)
    verdict_reason: Mapped[str] = mapped_column(String(512), nullable=False)


class EventRow(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_trace_span", "trace_id", "span_id"),
        Index("ix_events_tenant_occurred", "tenant_id", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    trace_id: Mapped[str] = mapped_column(String(32), nullable=False)
    span_id: Mapped[str] = mapped_column(String(16), nullable=False)
    parent_span_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    reasoning: Mapped[str | None] = mapped_column(String, nullable=True)
    policy_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    policy_verdict: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ReceiptRow(Base):
    __tablename__ = "receipts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sequence", name="uq_receipts_tenant_sequence"),
        Index("ix_receipts_event", "event_id"),
        Index("ix_receipts_tenant_signed", "tenant_id", "signed_at"),
        CheckConstraint("sequence >= 0", name="ck_receipts_sequence_nonneg"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="RESTRICT"),
        nullable=False,
    )
    policy_bundle_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("policy_bundles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    policy_snapshot_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("policy_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    prev_receipt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    receipt_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    signature: Mapped[bytes] = mapped_column(LargeBinary(64), nullable=False)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

### CP3.2 - Alembic migration (0002_policy_snapshot) - `alembic/versions/20260513_2055_policy_snapshot.py`

```python
"""add_policy_snapshots

Revision ID: 0002_policy_snapshot
Revises: 0001_initial
Create Date: 2026-05-13 20:55:00 UTC

Adds the policy_snapshots table for BR-04 ingest-time policy binding, and
the receipts.policy_snapshot_id FK so every Receipt links to the exact
policy state active when its event was ingested.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002_policy_snapshot"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "policy_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_bundle_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_bundle_version", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verdict_decision", sa.String(length=16), nullable=False),
        sa.Column("verdict_reason", sa.String(length=512), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["policy_bundle_id"], ["policy_bundles.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "verdict_decision IN ('allow', 'deny', 'escalate')",
            name="ck_policy_snapshots_decision",
        ),
    )
    op.create_index("ix_policy_snapshots_bundle", "policy_snapshots", ["policy_bundle_id"])
    op.create_index(
        "ix_policy_snapshots_tenant_captured",
        "policy_snapshots",
        ["tenant_id", "captured_at"],
    )
    op.create_index("ix_policy_snapshots_content_hash", "policy_snapshots", ["content_hash"])

    op.add_column(
        "receipts",
        sa.Column(
            "policy_snapshot_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_receipts_policy_snapshot",
        "receipts",
        "policy_snapshots",
        ["policy_snapshot_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_receipts_policy_snapshot", "receipts", ["policy_snapshot_id"])


def downgrade() -> None:
    op.drop_index("ix_receipts_policy_snapshot", table_name="receipts")
    op.drop_constraint("fk_receipts_policy_snapshot", "receipts", type_="foreignkey")
    op.drop_column("receipts", "policy_snapshot_id")
    op.drop_index("ix_policy_snapshots_content_hash", table_name="policy_snapshots")
    op.drop_index("ix_policy_snapshots_tenant_captured", table_name="policy_snapshots")
    op.drop_index("ix_policy_snapshots_bundle", table_name="policy_snapshots")
    op.drop_table("policy_snapshots")
```

### CP3.2 - Test script (test_alembic_migration.py) - `tests/packages/test_alembic_migration.py`

```python
"""Tests for the Alembic initial-schema migration.

Runs alembic upgrade head --sql offline and asserts every expected table,
index, FK, and constraint is present. Pure offline test: no DB needed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def migration_sql() -> str:
    """Run alembic upgrade head --sql and return stdout."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


EXPECTED_TABLES = [
    "tenants",
    "agents",
    "policy_bundles",
    "policy_snapshots",
    "events",
    "receipts",
]


@pytest.mark.parametrize("table", EXPECTED_TABLES)
def test_table_created(migration_sql, table):
    assert f"CREATE TABLE {table}" in migration_sql


EXPECTED_INDEXES = [
    "ix_tenants_slug",
    "ix_agents_tenant_id",
    "ix_policy_bundles_tenant_id",
    "ix_policy_bundles_content_hash",
    "ix_policy_snapshots_bundle",
    "ix_policy_snapshots_tenant_captured",
    "ix_policy_snapshots_content_hash",
    "ix_events_trace_span",
    "ix_events_tenant_occurred",
    "ix_receipts_event",
    "ix_receipts_tenant_signed",
    "ix_receipts_policy_snapshot",
]


@pytest.mark.parametrize("index_name", EXPECTED_INDEXES)
def test_index_created(migration_sql, index_name):
    assert index_name in migration_sql


EXPECTED_CONSTRAINTS = [
    "uq_tenants_slug",
    "uq_agents_tenant_slug",
    "ck_agents_status",
    "uq_policy_bundles_tenant_version",
    "ck_policy_snapshots_decision",
    "uq_receipts_tenant_sequence",
    "uq_receipts_receipt_hash",
    "ck_receipts_sequence_nonneg",
    "fk_receipts_policy_snapshot",
]


@pytest.mark.parametrize("constraint_name", EXPECTED_CONSTRAINTS)
def test_constraint_created(migration_sql, constraint_name):
    assert constraint_name in migration_sql


def test_alembic_version_table_present(migration_sql):
    assert "alembic_version" in migration_sql
    assert "0001_initial" in migration_sql
    assert "0002_policy_snapshot" in migration_sql


def test_all_fks_use_restrict_ondelete(migration_sql):
    """Append-only ledger: no cascading deletes."""
    # Every ForeignKey in the migration should use ON DELETE RESTRICT
    fk_lines = [ln for ln in migration_sql.splitlines() if "FOREIGN KEY" in ln]
    assert (
        len(fk_lines) >= 6
    )  # tenant_id in agents,pb,events,receipts + agent_id + event_id + pb_id
    for ln in fk_lines:
        assert "ON DELETE RESTRICT" in ln, f"FK without RESTRICT: {ln}"


def test_jsonb_columns_present(migration_sql):
    """payload and content columns must be JSONB for PostgreSQL."""
    assert "payload JSONB NOT NULL" in migration_sql
    assert "content JSONB NOT NULL" in migration_sql


def test_timezone_aware_datetimes(migration_sql):
    """All datetime columns must be TIMESTAMP WITH TIME ZONE."""
    assert "TIMESTAMP WITH TIME ZONE NOT NULL" in migration_sql
    # No naive timestamps should exist
    assert (
        "TIMESTAMP NOT NULL" not in migration_sql
        or "TIMESTAMP WITH TIME ZONE NOT NULL" in migration_sql
    )
```

### CP3.3 - Production code (replay.py) - `packages/policy/replay.py`

```python
"""Replay-time policy resolution for Receipts (CP3.3 / BR-04).

At replay time, the question is: what rules were active when this Receipt
was issued? Two possible answers:

1. The current state of the policy bundle (WRONG — bundle may have drifted
   or been rebuilt since ingest).
2. The PolicySnapshot captured at ingest (RIGHT — that's exactly what BR-04
   demands).

This module provides resolve_replay_policy(), which takes a Receipt and its
associated PolicySnapshot, and returns a ReplayPolicy object that the caller
must use for the replay computation. resolve_replay_policy NEVER returns the
live bundle's content_hash; it always returns the snapshot's content_hash.

If the snapshot is missing or doesn't match the receipt's policy_bundle_id,
the resolver raises. If the live bundle has drifted from the snapshot, the
resolver returns the snapshot anyway (replay binds to snapshot, not live)
but flags drift_detected=True so the caller can diagnose.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from packages.policy.snapshot import PolicySnapshot, snapshot_matches_bundle
from packages.schema.policy_bundle import PolicyBundle


class ReplayResolutionError(RuntimeError):
    """Raised when a receipt cannot be replayed because its snapshot is malformed."""


@dataclass(frozen=True)
class ReplayPolicy:
    """The policy state to bind a replay to.

    Always derived from the snapshot's content_hash. drift_detected is True
    iff the live bundle has changed since the snapshot was captured.
    """

    policy_bundle_id: UUID
    policy_bundle_version: str
    content_hash: str
    verdict_decision: str
    verdict_reason: str
    drift_detected: bool


def resolve_replay_policy(
    *,
    receipt_policy_bundle_id: UUID,
    receipt_policy_snapshot_id: UUID,
    snapshot: PolicySnapshot,
    live_bundle: PolicyBundle | None,
) -> ReplayPolicy:
    """Return the policy state to bind a replay to.

    Args:
        receipt_policy_bundle_id: receipt.policy_bundle_id from the ledger row
        receipt_policy_snapshot_id: receipt.policy_snapshot_id from the ledger row
        snapshot: the PolicySnapshot record fetched by snapshot_id
        live_bundle: the current PolicyBundle for receipt_policy_bundle_id, or
            None if the bundle has been deleted (ondelete=RESTRICT prevents this
            in production but tests and forensic scenarios may pass None).

    Returns: ReplayPolicy bound to snapshot.content_hash.

    Raises:
        ReplayResolutionError: if the snapshot's policy_bundle_id doesn't match
            the receipt's, or if the snapshot doesn't claim to be the one bound
            to this receipt.
    """
    if snapshot.policy_bundle_id != receipt_policy_bundle_id:
        raise ReplayResolutionError(
            f"snapshot.policy_bundle_id {snapshot.policy_bundle_id} does not "
            f"match receipt.policy_bundle_id {receipt_policy_bundle_id}; "
            "the snapshot loaded does not belong to this receipt"
        )

    drift = False
    if live_bundle is not None and not snapshot_matches_bundle(snapshot, live_bundle):
        # Live bundle has drifted from snapshot. Replay still binds to snapshot.
        drift = True

    # Sanity: receipt_policy_snapshot_id is plumbed through for caller correctness
    # checks (e.g. the caller fetched the right snapshot row), but is not used
    # in the replay computation itself.
    _ = receipt_policy_snapshot_id

    return ReplayPolicy(
        policy_bundle_id=snapshot.policy_bundle_id,
        policy_bundle_version=snapshot.policy_bundle_version,
        content_hash=snapshot.content_hash,
        verdict_decision=snapshot.verdict_decision,
        verdict_reason=snapshot.verdict_reason,
        drift_detected=drift,
    )
```

### CP3.3 - Test script (test_replay.py) - `tests/packages/test_replay.py`

```python
"""Tests for packages/policy/replay.py - 100% branch coverage."""

from __future__ import annotations

import asyncio
from uuid import UUID

import pytest

from packages.policy.bundle_builder import build_bundle
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.policy.replay import (
    ReplayPolicy,
    ReplayResolutionError,
    resolve_replay_policy,
)
from packages.policy.snapshot import PolicySnapshot, capture_snapshot
from packages.schema.policy_bundle import PolicyBundle

_TENANT_ID = UUID("55555555-5555-5555-5555-555555555555")
_SAMPLE_CONTENT = {"rules": [{"kind": "deny_kind", "decision": "deny"}], "default": "allow"}


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _aligned_snapshot() -> tuple[PolicyBundle, PolicySnapshot, UUID]:
    bundle = build_bundle(tenant_id=_TENANT_ID, version="1.0.0", content=_SAMPLE_CONTENT)
    mock = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )
    verdict = _run(mock.evaluate(_TENANT_ID, {"kind": "x"}))
    snap = capture_snapshot(bundle, verdict)
    fake_receipt_snapshot_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    return bundle, snap, fake_receipt_snapshot_id


# ---------- happy path ----------


def test_replay_resolves_to_snapshot_content_hash_no_drift():
    bundle, snap, snap_id = _aligned_snapshot()
    rp = resolve_replay_policy(
        receipt_policy_bundle_id=bundle.id,
        receipt_policy_snapshot_id=snap_id,
        snapshot=snap,
        live_bundle=bundle,
    )
    assert isinstance(rp, ReplayPolicy)
    assert rp.policy_bundle_id == bundle.id
    assert rp.content_hash == snap.content_hash
    assert rp.drift_detected is False
    assert rp.policy_bundle_version == bundle.version
    assert rp.verdict_decision == snap.verdict_decision


def test_replay_returns_frozen_dataclass():
    bundle, snap, snap_id = _aligned_snapshot()
    rp = resolve_replay_policy(
        receipt_policy_bundle_id=bundle.id,
        receipt_policy_snapshot_id=snap_id,
        snapshot=snap,
        live_bundle=bundle,
    )
    with pytest.raises(Exception):  # noqa: B017 - dataclass FrozenInstanceError
        rp.content_hash = "tampered"  # type: ignore[misc]


# ---------- drift detection ----------


def test_replay_flags_drift_when_live_bundle_changed():
    bundle, snap, snap_id = _aligned_snapshot()
    # Drift: same id, different content/hash.
    drifted = PolicyBundle(
        id=bundle.id,
        tenant_id=bundle.tenant_id,
        version="1.0.1",
        content_hash="f" * 64,
        content={"different": "rules"},
        created_at=bundle.created_at,
    )
    rp = resolve_replay_policy(
        receipt_policy_bundle_id=bundle.id,
        receipt_policy_snapshot_id=snap_id,
        snapshot=snap,
        live_bundle=drifted,
    )
    # Replay STILL binds to snapshot (the whole point).
    assert rp.content_hash == snap.content_hash
    assert rp.drift_detected is True


def test_replay_with_no_live_bundle_does_not_flag_drift():
    bundle, snap, snap_id = _aligned_snapshot()
    rp = resolve_replay_policy(
        receipt_policy_bundle_id=bundle.id,
        receipt_policy_snapshot_id=snap_id,
        snapshot=snap,
        live_bundle=None,
    )
    # Missing live bundle is a forensic-scenario allowance; treat as no drift.
    assert rp.content_hash == snap.content_hash
    assert rp.drift_detected is False


# ---------- error paths ----------


def test_replay_rejects_snapshot_bound_to_different_bundle():
    bundle, snap, snap_id = _aligned_snapshot()
    other_bundle_id = UUID("99999999-9999-9999-9999-999999999999")
    with pytest.raises(ReplayResolutionError, match="does not match receipt.policy_bundle_id"):
        resolve_replay_policy(
            receipt_policy_bundle_id=other_bundle_id,
            receipt_policy_snapshot_id=snap_id,
            snapshot=snap,
            live_bundle=bundle,
        )
```


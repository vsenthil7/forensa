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

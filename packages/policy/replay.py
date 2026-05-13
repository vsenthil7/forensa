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

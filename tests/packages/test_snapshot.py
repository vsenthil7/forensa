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

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

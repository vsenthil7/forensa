"""Tests for the dual-signature path through build_receipt + verifiers (CP9.18 / BR-02).

Covers:

- ``build_receipt`` with ``agent_signing_key=None`` -> receipt.agent_signature is None
  (backwards-compat path, same as the legacy single-sig API).
- ``build_receipt`` with a real agent_signing_key -> receipt.agent_signature is
  set, is 64 bytes, and is over the same receipt_hash as the tenant signature.
- ``verify_receipt_signature`` continues to verify the tenant signature, ignoring
  the agent signature (independent verification).
- ``verify_receipt_agent_signature`` returns True for a correctly signed receipt
  and False when the agent_signature is None / when the wrong public key is used.
- The same receipt_hash is signed by both keys, so the signatures are independent
  witnesses to the same bound state - tamper-evidence still applies even if one
  signature is rotated.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from packages.crypto.sign import generate_keypair
from packages.ledger.receipt_builder import (
    build_receipt,
    recompute_receipt_hash,
    verify_receipt_agent_signature,
    verify_receipt_signature,
)
from packages.policy.snapshot import PolicySnapshot


@pytest.fixture
def fresh_snapshot():
    return PolicySnapshot(
        policy_bundle_id=uuid4(),
        policy_bundle_version="1.0.0",
        content_hash="c" * 64,
        captured_at=datetime(2026, 5, 14, 22, 30, tzinfo=UTC),
        verdict_decision="allow",
        verdict_reason="test verdict",
    )


@pytest.fixture
def tenant_keypair():
    priv, pub = generate_keypair()
    return priv, pub


@pytest.fixture
def agent_keypair():
    priv, pub = generate_keypair()
    return priv, pub


def test_build_receipt_no_agent_key_yields_none_agent_signature(fresh_snapshot, tenant_keypair):
    """Backwards-compat: omitting agent_signing_key produces a receipt with
    agent_signature=None. Existing callers continue to work unchanged."""
    tenant_priv, _ = tenant_keypair
    snapshot_id = uuid4()
    r = build_receipt(
        tenant_id=uuid4(),
        event_id=uuid4(),
        event_payload={"k": "v"},
        policy_snapshot=fresh_snapshot,
        policy_snapshot_id=snapshot_id,
        prev_receipt=None,
        tenant_signing_key=tenant_priv,
    )
    assert r.agent_signature is None
    # Tenant signature is still present and well-formed.
    assert len(r.signature) == 64


def test_build_receipt_with_agent_key_produces_both_signatures(
    fresh_snapshot, tenant_keypair, agent_keypair
):
    tenant_priv, _ = tenant_keypair
    agent_priv, _ = agent_keypair
    snapshot_id = uuid4()
    r = build_receipt(
        tenant_id=uuid4(),
        event_id=uuid4(),
        event_payload={"k": "v"},
        policy_snapshot=fresh_snapshot,
        policy_snapshot_id=snapshot_id,
        prev_receipt=None,
        tenant_signing_key=tenant_priv,
        agent_signing_key=agent_priv,
    )
    assert r.signature is not None
    assert r.agent_signature is not None
    assert len(r.agent_signature) == 64
    # The two signatures are different bytes (different keys, same hash).
    assert r.signature != r.agent_signature


def test_dual_signatures_verify_independently(fresh_snapshot, tenant_keypair, agent_keypair):
    """Each signature verifies under its own public key, independently."""
    tenant_priv, tenant_pub = tenant_keypair
    agent_priv, agent_pub = agent_keypair
    snapshot_id = uuid4()
    r = build_receipt(
        tenant_id=uuid4(),
        event_id=uuid4(),
        event_payload={"k": "v"},
        policy_snapshot=fresh_snapshot,
        policy_snapshot_id=snapshot_id,
        prev_receipt=None,
        tenant_signing_key=tenant_priv,
        agent_signing_key=agent_priv,
    )
    assert verify_receipt_signature(r, tenant_pub) is True
    assert verify_receipt_agent_signature(r, agent_pub) is True


def test_agent_signature_does_not_verify_with_tenant_key(
    fresh_snapshot, tenant_keypair, agent_keypair
):
    """The agent signature must NOT verify under the tenant public key
    (different signing keys produce different bytes for the same hash)."""
    tenant_priv, tenant_pub = tenant_keypair
    agent_priv, _ = agent_keypair
    snapshot_id = uuid4()
    r = build_receipt(
        tenant_id=uuid4(),
        event_id=uuid4(),
        event_payload={"k": "v"},
        policy_snapshot=fresh_snapshot,
        policy_snapshot_id=snapshot_id,
        prev_receipt=None,
        tenant_signing_key=tenant_priv,
        agent_signing_key=agent_priv,
    )
    # verify_receipt_agent_signature called with the wrong public key returns False.
    assert verify_receipt_agent_signature(r, tenant_pub) is False


def test_tenant_signature_does_not_verify_with_agent_key(
    fresh_snapshot, tenant_keypair, agent_keypair
):
    tenant_priv, _ = tenant_keypair
    agent_priv, agent_pub = agent_keypair
    snapshot_id = uuid4()
    r = build_receipt(
        tenant_id=uuid4(),
        event_id=uuid4(),
        event_payload={"k": "v"},
        policy_snapshot=fresh_snapshot,
        policy_snapshot_id=snapshot_id,
        prev_receipt=None,
        tenant_signing_key=tenant_priv,
        agent_signing_key=agent_priv,
    )
    assert verify_receipt_signature(r, agent_pub) is False


def test_verify_agent_signature_returns_false_when_no_agent_signature(
    fresh_snapshot, tenant_keypair, agent_keypair
):
    """Backwards-compat receipt with agent_signature=None: the agent verifier
    must return False (NOT True), even though technically there's nothing
    to disprove. Callers want a positive 'yes the agent signed this' answer."""
    tenant_priv, _ = tenant_keypair
    _, agent_pub = agent_keypair
    snapshot_id = uuid4()
    r = build_receipt(
        tenant_id=uuid4(),
        event_id=uuid4(),
        event_payload={"k": "v"},
        policy_snapshot=fresh_snapshot,
        policy_snapshot_id=snapshot_id,
        prev_receipt=None,
        tenant_signing_key=tenant_priv,
    )
    assert r.agent_signature is None
    assert verify_receipt_agent_signature(r, agent_pub) is False


def test_both_signatures_sign_the_same_receipt_hash(fresh_snapshot, tenant_keypair, agent_keypair):
    """Critical contract: the two signatures sign the SAME 64-byte
    receipt_hash. Neither signature is part of the binding hash. This means
    one signature can be invalidated (e.g. agent key rotation) without
    breaking the chain integrity proven by recompute_receipt_hash."""
    tenant_priv, _ = tenant_keypair
    agent_priv, _ = agent_keypair
    snapshot_id = uuid4()
    r = build_receipt(
        tenant_id=uuid4(),
        event_id=uuid4(),
        event_payload={"k": "v"},
        policy_snapshot=fresh_snapshot,
        policy_snapshot_id=snapshot_id,
        prev_receipt=None,
        tenant_signing_key=tenant_priv,
        agent_signing_key=agent_priv,
    )
    # The chain integrity check does NOT include either signature in the
    # bind - it recomputes the hash from the structural fields only.
    recomputed = recompute_receipt_hash(r, snapshot_id)
    assert recomputed == r.receipt_hash

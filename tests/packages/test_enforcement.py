"""Tests for packages/policy/enforcement.py - vendor-neutral abstraction (CP9.5).

Coverage targets:

- PolicyDecision enum surface
- PolicyEnforcementError class identity
- PolicyVerdict __post_init__ validation paths (all 4 branches)
- PolicyEnforcementClient is abstract
- Legacy aliases (LobsterTrapClient / LobsterTrapError) are the SAME class
  object as the canonical names (not just structurally equivalent)
- A MockLobsterTrapClient instance is recognised by both legacy and canonical
  isinstance checks
- VeeaLobsterTrapClient is the vendor-facade alias
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from packages.policy import (
    PolicyDecision,
    PolicyEnforcementClient,
    PolicyEnforcementError,
    PolicyVerdict,
)
from packages.policy.enforcement import (
    PolicyDecision as PolicyDecisionDirect,
)
from packages.policy.enforcement import (
    PolicyEnforcementClient as PolicyEnforcementClientDirect,
)
from packages.policy.enforcement import (
    PolicyEnforcementError as PolicyEnforcementErrorDirect,
)
from packages.policy.enforcement import (
    PolicyVerdict as PolicyVerdictDirect,
)
from packages.policy.lobstertrap import (
    LobsterTrapClient,
    LobsterTrapError,
    MockLobsterTrapClient,
    VeeaLobsterTrapClient,
)

_VALID_HASH = "a" * 64


# ---------- canonical names are re-exported from the package root ----------


def test_package_root_re_exports_canonical_names():
    assert PolicyDecision is PolicyDecisionDirect
    assert PolicyVerdict is PolicyVerdictDirect
    assert PolicyEnforcementClient is PolicyEnforcementClientDirect
    assert PolicyEnforcementError is PolicyEnforcementErrorDirect


# ---------- legacy aliases ARE the canonical classes (object identity) ----------


def test_legacy_aliases_are_canonical_classes():
    """LobsterTrapClient and PolicyEnforcementClient must be the SAME class
    object so isinstance() works through either name and no double-dispatch
    surprises occur at the type system level."""
    assert LobsterTrapClient is PolicyEnforcementClient
    assert LobsterTrapError is PolicyEnforcementError


def test_concrete_mock_is_recognised_by_both_names():
    """A MockLobsterTrapClient instance must satisfy isinstance for BOTH
    the canonical PolicyEnforcementClient and the legacy LobsterTrapClient."""
    mock = MockLobsterTrapClient(policy_bundle_id=uuid4())
    assert isinstance(mock, PolicyEnforcementClient)
    assert isinstance(mock, LobsterTrapClient)


def test_veea_facade_is_alias_for_mock_today():
    """VeeaLobsterTrapClient is the vendor-named facade. Today it is an alias
    for the mock until the real Veea HTTP client lands; the alias makes the
    vendor-neutral abstraction visible without inventing fake code."""
    assert VeeaLobsterTrapClient is MockLobsterTrapClient


# ---------- PolicyDecision enum surface ----------


def test_policy_decision_values():
    assert PolicyDecision.ALLOW.value == "allow"
    assert PolicyDecision.DENY.value == "deny"
    assert PolicyDecision.ESCALATE.value == "escalate"


def test_policy_decision_is_string_subclass():
    """PolicyDecision is `str, Enum` so equality with plain strings works
    (the legacy contract some callers rely on)."""
    assert PolicyDecision.ALLOW == "allow"
    assert PolicyDecision.DENY == "deny"


# ---------- PolicyEnforcementError class identity ----------


def test_policy_enforcement_error_is_runtime_error():
    err = PolicyEnforcementError("upstream timed out")
    assert isinstance(err, RuntimeError)
    assert str(err) == "upstream timed out"


# ---------- PolicyEnforcementClient is abstract ----------


def test_enforcement_client_is_abstract():
    with pytest.raises(TypeError):
        PolicyEnforcementClient()  # type: ignore[abstract]


# ---------- PolicyVerdict __post_init__ validation ----------


def test_verdict_accepts_well_formed_inputs():
    v = PolicyVerdict(
        decision=PolicyDecision.ALLOW,
        policy_bundle_id=uuid4(),
        policy_bundle_version="1.0.0",
        content_hash=_VALID_HASH,
        reason="ok",
    )
    assert v.decision is PolicyDecision.ALLOW


def test_verdict_rejects_non_enum_decision():
    with pytest.raises(TypeError, match="decision must be PolicyDecision"):
        PolicyVerdict(
            decision="allow",  # type: ignore[arg-type]
            policy_bundle_id=uuid4(),
            policy_bundle_version="1.0.0",
            content_hash=_VALID_HASH,
            reason="ok",
        )


def test_verdict_rejects_naive_evaluated_at():
    with pytest.raises(ValueError, match="evaluated_at must be timezone-aware"):
        PolicyVerdict(
            decision=PolicyDecision.ALLOW,
            policy_bundle_id=uuid4(),
            policy_bundle_version="1.0.0",
            content_hash=_VALID_HASH,
            reason="ok",
            evaluated_at=datetime(2026, 5, 14, 14, 38),  # naive
        )


def test_verdict_rejects_short_content_hash():
    with pytest.raises(ValueError, match="content_hash must be 64-char lowercase hex"):
        PolicyVerdict(
            decision=PolicyDecision.ALLOW,
            policy_bundle_id=uuid4(),
            policy_bundle_version="1.0.0",
            content_hash="abc",
            reason="ok",
        )


def test_verdict_rejects_non_hex_content_hash():
    with pytest.raises(ValueError, match="content_hash must be 64-char lowercase hex"):
        PolicyVerdict(
            decision=PolicyDecision.ALLOW,
            policy_bundle_id=uuid4(),
            policy_bundle_version="1.0.0",
            content_hash="g" * 64,  # not hex
            reason="ok",
        )


def test_verdict_rejects_empty_reason():
    with pytest.raises(ValueError, match="reason must be a non-empty string"):
        PolicyVerdict(
            decision=PolicyDecision.ALLOW,
            policy_bundle_id=uuid4(),
            policy_bundle_version="1.0.0",
            content_hash=_VALID_HASH,
            reason="",
        )


def test_verdict_default_evaluated_at_is_tz_aware_utc():
    v = PolicyVerdict(
        decision=PolicyDecision.ALLOW,
        policy_bundle_id=uuid4(),
        policy_bundle_version="1.0.0",
        content_hash=_VALID_HASH,
        reason="ok",
    )
    assert v.evaluated_at.tzinfo is UTC


def test_verdict_is_frozen():
    v = PolicyVerdict(
        decision=PolicyDecision.ALLOW,
        policy_bundle_id=uuid4(),
        policy_bundle_version="1.0.0",
        content_hash=_VALID_HASH,
        reason="ok",
    )
    with pytest.raises(AttributeError):
        v.decision = PolicyDecision.DENY  # type: ignore[misc]

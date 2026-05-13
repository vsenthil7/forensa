"""Tests for packages/policy/lobstertrap.py - 100% branch coverage.

Unit + property tests covering:
- PolicyDecision enum values
- PolicyVerdict immutability, validation (decision type, naive datetime, hash format, empty reason)
- LobsterTrapClient is abstract (cannot instantiate without implementing evaluate)
- MockLobsterTrapClient: allow / deny / escalate paths, custom content -> different content_hash,
  default vs custom version, latency_ms positive sleep + negative rejection, action must be dict
- LobsterTrapError class identity
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from packages.crypto.hash import sha256_hex
from packages.policy.lobstertrap import (
    LobsterTrapClient,
    LobsterTrapError,
    MockLobsterTrapClient,
    PolicyDecision,
    PolicyVerdict,
)

_GOOD_HASH = "a" * 64
_BUNDLE_ID = UUID("11111111-1111-1111-1111-111111111111")
_TENANT_ID = UUID("22222222-2222-2222-2222-222222222222")


# ---------- PolicyDecision ----------


def test_policy_decision_values():
    assert PolicyDecision.ALLOW.value == "allow"
    assert PolicyDecision.DENY.value == "deny"
    assert PolicyDecision.ESCALATE.value == "escalate"


# ---------- PolicyVerdict ----------


def _good_verdict(**over):
    base = dict(
        decision=PolicyDecision.ALLOW,
        policy_bundle_id=_BUNDLE_ID,
        policy_bundle_version="1.0.0",
        content_hash=_GOOD_HASH,
        reason="ok",
    )
    base.update(over)
    return PolicyVerdict(**base)


def test_policy_verdict_minimal_valid():
    v = _good_verdict()
    assert v.decision is PolicyDecision.ALLOW
    assert v.policy_bundle_id == _BUNDLE_ID
    assert v.content_hash == _GOOD_HASH
    assert v.reason == "ok"
    assert v.evaluated_at.tzinfo is not None


def test_policy_verdict_is_frozen():
    v = _good_verdict()
    with pytest.raises(Exception):  # noqa: B017 - dataclass FrozenInstanceError
        v.reason = "tampered"  # type: ignore[misc]


def test_policy_verdict_rejects_non_enum_decision():
    with pytest.raises(TypeError, match="decision must be PolicyDecision"):
        PolicyVerdict(
            decision="allow",  # type: ignore[arg-type]
            policy_bundle_id=_BUNDLE_ID,
            policy_bundle_version="1.0.0",
            content_hash=_GOOD_HASH,
            reason="ok",
        )


def test_policy_verdict_rejects_naive_datetime():
    with pytest.raises(ValueError, match="must be timezone-aware"):
        PolicyVerdict(
            decision=PolicyDecision.ALLOW,
            policy_bundle_id=_BUNDLE_ID,
            policy_bundle_version="1.0.0",
            content_hash=_GOOD_HASH,
            reason="ok",
            evaluated_at=datetime(2026, 5, 13, 15, 0),
        )


def test_policy_verdict_accepts_non_utc_tz():
    tz = timezone(timedelta(hours=5, minutes=30))
    v = _good_verdict(evaluated_at=datetime(2026, 5, 13, 15, 0, tzinfo=tz))
    assert v.evaluated_at.utcoffset() == timedelta(hours=5, minutes=30)


def test_policy_verdict_rejects_short_hash():
    with pytest.raises(ValueError, match="must be 64-char lowercase hex"):
        _good_verdict(content_hash="abc")


def test_policy_verdict_rejects_uppercase_hash():
    with pytest.raises(ValueError, match="must be 64-char lowercase hex"):
        _good_verdict(content_hash="A" * 64)


def test_policy_verdict_rejects_empty_reason():
    with pytest.raises(ValueError, match="reason must be a non-empty"):
        _good_verdict(reason="")


# ---------- LobsterTrapClient is abstract ----------


def test_lobstertrap_client_is_abstract():
    with pytest.raises(TypeError, match="abstract"):
        LobsterTrapClient()  # type: ignore[abstract]


# ---------- MockLobsterTrapClient ----------


def _mock(**over) -> MockLobsterTrapClient:
    base = dict(policy_bundle_id=_BUNDLE_ID)
    base.update(over)
    return MockLobsterTrapClient(**base)


def test_mock_allow_for_unrecognised_kind():
    mock = _mock()
    v = asyncio.run(mock.evaluate(_TENANT_ID, {"kind": "anything_else"}))
    assert v.decision is PolicyDecision.ALLOW
    assert "no matching" in v.reason


def test_mock_allow_when_no_kind_field():
    mock = _mock()
    v = asyncio.run(mock.evaluate(_TENANT_ID, {"other": "field"}))
    assert v.decision is PolicyDecision.ALLOW


def test_mock_deny_for_deny_kind():
    mock = _mock()
    v = asyncio.run(mock.evaluate(_TENANT_ID, {"kind": "deny_kind"}))
    assert v.decision is PolicyDecision.DENY
    assert v.reason == "matched rule deny_kind"


def test_mock_escalate_for_escalate_kind():
    mock = _mock()
    v = asyncio.run(mock.evaluate(_TENANT_ID, {"kind": "escalate_kind"}))
    assert v.decision is PolicyDecision.ESCALATE


def test_mock_binds_policy_bundle_into_verdict():
    mock = _mock(policy_bundle_version="2.1.0")
    v = asyncio.run(mock.evaluate(_TENANT_ID, {"kind": "x"}))
    assert v.policy_bundle_id == _BUNDLE_ID
    assert v.policy_bundle_version == "2.1.0"
    assert v.content_hash == mock.content_hash


def test_mock_content_hash_is_deterministic_for_default_content():
    a = _mock()
    b = _mock()
    assert a.content_hash == b.content_hash


def test_mock_custom_content_changes_content_hash():
    custom = {"rules": [], "default": "allow"}
    mock = _mock(content=custom)
    assert mock.content_hash == sha256_hex(custom)
    assert mock.content_hash != MockLobsterTrapClient(_BUNDLE_ID).content_hash


def test_mock_rejects_negative_latency():
    with pytest.raises(ValueError, match="latency_ms must be >= 0"):
        _mock(latency_ms=-1)


def test_mock_applies_latency_when_positive():
    mock = _mock(latency_ms=20)
    start = time.perf_counter()
    asyncio.run(mock.evaluate(_TENANT_ID, {"kind": "x"}))
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms >= 18  # allow scheduler slack


def test_mock_rejects_non_dict_action():
    mock = _mock()
    with pytest.raises(TypeError, match="action must be a dict"):
        asyncio.run(mock.evaluate(_TENANT_ID, "not a dict"))  # type: ignore[arg-type]


# ---------- LobsterTrapError ----------


def test_lobstertrap_error_is_runtime_error():
    err = LobsterTrapError("trap timed out")
    assert isinstance(err, RuntimeError)
    assert str(err) == "trap timed out"


# ---------- Hypothesis property tests ----------


@given(
    st.sampled_from(["deny_kind", "escalate_kind", "allow_other", "", "foo"]),
)
def test_mock_decision_is_deterministic_per_kind(kind):
    """For a fixed kind, the mock always returns the same decision."""
    mock_a = _mock()
    mock_b = _mock()
    va = asyncio.run(mock_a.evaluate(_TENANT_ID, {"kind": kind}))
    vb = asyncio.run(mock_b.evaluate(_TENANT_ID, {"kind": kind}))
    assert va.decision is vb.decision
    assert va.content_hash == vb.content_hash


@given(st.text(min_size=0, max_size=20))
def test_mock_verdict_always_bound_to_bundle(kind_text):
    """Every verdict carries the configured policy_bundle_id and version."""
    mock = _mock(policy_bundle_version="9.9.9")
    v = asyncio.run(mock.evaluate(_TENANT_ID, {"kind": kind_text}))
    assert v.policy_bundle_id == _BUNDLE_ID
    assert v.policy_bundle_version == "9.9.9"

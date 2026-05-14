"""Veea Lobster Trap enforcement adapter for Forensa.

The Lobster Trap is the Veea-provided runtime enforcement gateway. This
module is one concrete adapter implementing
``packages.policy.enforcement.PolicyEnforcementClient`` - the
vendor-neutral abstraction every enforcement integration must satisfy.

Vendor-neutral surface
----------------------

The types ``PolicyDecision``, ``PolicyVerdict``, ``PolicyEnforcementClient``,
and ``PolicyEnforcementError`` are defined in
``packages.policy.enforcement`` and re-exported here under both their
canonical (vendor-neutral) names AND their legacy (Veea-named) aliases:

| Canonical name            | Legacy alias        |
|---------------------------|---------------------|
| ``PolicyDecision``        | ``PolicyDecision``  |
| ``PolicyVerdict``         | ``PolicyVerdict``   |
| ``PolicyEnforcementClient`` | ``LobsterTrapClient`` |
| ``PolicyEnforcementError``  | ``LobsterTrapError``  |

Existing callers (13 test files + ``packages/policy/snapshot.py``) keep
working unchanged. New callers should import the canonical names from
``packages.policy.enforcement`` (or via ``packages.policy``).

Concrete classes
----------------

- ``MockLobsterTrapClient``: deterministic in-memory mock used by tests
  and demo. Surface is unchanged from the pre-CP9.5 implementation.
- ``VeeaLobsterTrapClient``: alias for ``MockLobsterTrapClient`` until the
  real Veea HTTP client lands. This makes the vendor-neutral abstraction
  visible immediately while keeping a single source of truth for the
  mock behaviour.

The future real Veea HTTP client (httpx with retry/timeout/circuit-breaker)
will replace this alias with a proper subclass; the wire-form contract
stays identical so callers do not change.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, ClassVar
from uuid import UUID

from packages.crypto.hash import sha256_hex
from packages.policy.enforcement import (
    PolicyDecision,
    PolicyEnforcementClient,
    PolicyEnforcementError,
    PolicyVerdict,
)

# ---------------------------------------------------------------------------
# Legacy aliases - keep all existing callers working unchanged.
# ---------------------------------------------------------------------------

# `LobsterTrapClient` and `LobsterTrapError` are the legacy names; the
# vendor-neutral names are `PolicyEnforcementClient` and
# `PolicyEnforcementError`. Both refer to the SAME class object so
# `isinstance(x, LobsterTrapClient)` and `isinstance(x, PolicyEnforcementClient)`
# are equivalent.
LobsterTrapClient = PolicyEnforcementClient
LobsterTrapError = PolicyEnforcementError


# `PolicyDecision`, `PolicyVerdict` are re-exported under their canonical
# names. They are already vendor-neutral; no separate alias is needed.

# Module-level holders so __all__ + import * keeps the legacy names visible.
_PolicyDecision = PolicyDecision
_PolicyVerdict = PolicyVerdict


# ---------------------------------------------------------------------------
# Concrete adapters
# ---------------------------------------------------------------------------


@dataclass(frozen=False)
class MockLobsterTrapClient(PolicyEnforcementClient):
    """Deterministic in-memory enforcement adapter for tests and demo.

    Backed by a small ruleset keyed on the action's ``kind`` field:
    - ``kind == "deny_kind"``     -> DENY
    - ``kind == "escalate_kind"`` -> ESCALATE
    - anything else               -> ALLOW

    Each verdict is bound to a stable mock policy bundle so the
    ``content_hash`` is deterministic across calls.
    """

    _DEFAULT_VERSION: ClassVar[str] = "1.0.0"
    _DEFAULT_CONTENT: ClassVar[dict[str, Any]] = {
        "rules": [
            {"kind": "deny_kind", "decision": "deny"},
            {"kind": "escalate_kind", "decision": "escalate"},
        ],
        "default": "allow",
    }

    def __init__(
        self,
        policy_bundle_id: UUID,
        policy_bundle_version: str = _DEFAULT_VERSION,
        content: dict[str, Any] | None = None,
        latency_ms: int = 0,
    ) -> None:
        self._policy_bundle_id = policy_bundle_id
        self._policy_bundle_version = policy_bundle_version
        self._content = content if content is not None else self._DEFAULT_CONTENT
        self._content_hash = sha256_hex(self._content)
        if latency_ms < 0:
            raise ValueError("latency_ms must be >= 0")
        self._latency_ms = latency_ms

    @property
    def content_hash(self) -> str:
        """The deterministic content_hash bound into every verdict."""
        return self._content_hash

    async def evaluate(self, tenant_id: UUID, action: dict[str, Any]) -> PolicyVerdict:
        if not isinstance(action, dict):
            raise TypeError(f"action must be a dict, got {type(action).__name__}")
        if self._latency_ms > 0:
            await asyncio.sleep(self._latency_ms / 1000.0)
        kind = action.get("kind")
        decision, reason = self._classify(kind)
        return PolicyVerdict(
            decision=decision,
            policy_bundle_id=self._policy_bundle_id,
            policy_bundle_version=self._policy_bundle_version,
            content_hash=self._content_hash,
            reason=reason,
        )

    @staticmethod
    def _classify(kind: Any) -> tuple[PolicyDecision, str]:
        if kind == "deny_kind":
            return PolicyDecision.DENY, "matched rule deny_kind"
        if kind == "escalate_kind":
            return PolicyDecision.ESCALATE, "matched rule escalate_kind"
        return PolicyDecision.ALLOW, "no matching deny/escalate rule"


# Vendor-neutral facade. Today this is just an alias because we don't yet
# have a real Veea HTTP client; when one lands it replaces this alias with
# a proper subclass of `PolicyEnforcementClient`.
VeeaLobsterTrapClient = MockLobsterTrapClient


__all__ = [
    # Canonical (vendor-neutral) re-exports
    "PolicyDecision",
    "PolicyEnforcementClient",
    "PolicyEnforcementError",
    "PolicyVerdict",
    # Legacy aliases - DO NOT remove without a deprecation cycle
    "LobsterTrapClient",
    "LobsterTrapError",
    # Concrete adapters
    "MockLobsterTrapClient",
    "VeeaLobsterTrapClient",
]

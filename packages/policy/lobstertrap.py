"""Lobster Trap policy verdict adapter for Forensa.

The Lobster Trap is the Veea-provided runtime enforcement gateway. Forensa
captures, evidences, and replays its verdicts; we do NOT make policy
decisions ourselves. This module defines:

- PolicyDecision: enum of allow / deny / escalate
- PolicyVerdict: an immutable dataclass with decision, policy_bundle_id,
  policy_bundle_version, content_hash, reason, evaluated_at
- LobsterTrapClient: abstract base for any Trap implementation
- MockLobsterTrapClient: deterministic in-memory mock used by tests and demo
- LobsterTrapError: raised when the Trap call fails after retries

The Trap is treated as an external service. Real implementations will use
httpx with retry/timeout. The mock implements the same surface so the rest
of Forensa never branches on real-vs-mock.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, ClassVar
from uuid import UUID

from packages.crypto.hash import sha256_hex


class PolicyDecision(str, Enum):
    """Trap verdict outcome."""

    ALLOW = "allow"
    DENY = "deny"
    ESCALATE = "escalate"


class LobsterTrapError(RuntimeError):
    """Raised when the Trap fails to return a verdict after retries."""


@dataclass(frozen=True)
class PolicyVerdict:
    """An immutable Lobster Trap verdict for a single agent action.

    Bound to the policy bundle that produced it (id, version, content_hash),
    so a Receipt can prove which rules were active when the verdict fired.
    """

    decision: PolicyDecision
    policy_bundle_id: UUID
    policy_bundle_version: str
    content_hash: str
    reason: str
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not isinstance(self.decision, PolicyDecision):
            raise TypeError(f"decision must be PolicyDecision, got {type(self.decision).__name__}")
        if self.evaluated_at.tzinfo is None:
            raise ValueError("evaluated_at must be timezone-aware (UTC)")
        if len(self.content_hash) != 64 or not all(
            c in "0123456789abcdef" for c in self.content_hash
        ):
            raise ValueError("content_hash must be 64-char lowercase hex (SHA-256)")
        if not self.reason:
            raise ValueError("reason must be a non-empty string")


class LobsterTrapClient(ABC):
    """Abstract Trap interface. All implementations honour this contract."""

    @abstractmethod
    async def evaluate(self, tenant_id: UUID, action: dict[str, Any]) -> PolicyVerdict:
        """Return a verdict for the given action.

        Implementations may retry transient errors; surface only terminal
        failures via LobsterTrapError.
        """


class MockLobsterTrapClient(LobsterTrapClient):
    """Deterministic in-memory Trap mock.

    Backed by a small ruleset keyed on the action's "kind" field:
    - kind == "deny_kind"      -> DENY
    - kind == "escalate_kind"  -> ESCALATE
    - anything else            -> ALLOW

    Each verdict is bound to a stable mock policy bundle so the
    content_hash is deterministic across calls.
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

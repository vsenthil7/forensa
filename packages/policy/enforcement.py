"""Vendor-neutral policy enforcement abstraction (CP9.5).

Forensa is an evidence layer, not an enforcement product. The enforcement
gateway is whatever the customer chose to run: today's reference partner is
Veea Lobster Trap; tomorrow's might be Microsoft AGT, AWS Bedrock AgentCore,
or a customer-built service. Forensa must not bind to any single vendor at
the type level - that's the procurement-credibility problem the
EnterpriseGradeReview Part 2 reservation 2 flagged.

This module defines the vendor-neutral surface every enforcement adapter
must implement:

- ``PolicyDecision``: enum of allow / deny / escalate
- ``PolicyVerdict``: an immutable dataclass binding the verdict to the
  policy bundle that produced it
- ``PolicyEnforcementClient``: abstract base every adapter implements
- ``PolicyEnforcementError``: raised when the enforcement call fails

The concrete Veea Lobster Trap implementation lives in
``packages/policy/lobstertrap.py`` (legacy module name; will move to
``packages/policy/veea_lobstertrap.py`` as part of NEW-P9.X.module-rename).
Other vendors land as their own subclasses without touching this module.

Backwards compatibility
-----------------------

The legacy module ``packages/policy/lobstertrap.py`` re-exports
``PolicyDecision``, ``PolicyVerdict``, ``PolicyEnforcementClient`` (as
``LobsterTrapClient``), and ``PolicyEnforcementError`` (as
``LobsterTrapError``) so existing callers keep working unchanged. The
migration of those callers is tracked as a separate CP.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID


class PolicyDecision(str, Enum):
    """Enforcement verdict outcome. Vendor-neutral."""

    ALLOW = "allow"
    DENY = "deny"
    ESCALATE = "escalate"


class PolicyEnforcementError(RuntimeError):
    """Raised when the enforcement adapter fails to return a verdict.

    Adapters surface only terminal failures (after retries) as this error;
    transient SDK / network problems must be retried inside the adapter.
    """


@dataclass(frozen=True)
class PolicyVerdict:
    """An immutable policy verdict for a single agent action.

    Bound to the policy bundle that produced it (id, version, content_hash)
    so a Receipt can prove which rules were active when the verdict fired.
    Vendor-neutral: any enforcement adapter returns this shape.
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


class PolicyEnforcementClient(ABC):
    """Abstract policy enforcement adapter.

    Implementations (one per enforcement vendor):
    - ``VeeaLobsterTrapClient`` -> ``packages/policy/lobstertrap.py``
      (legacy module name; concrete class is ``MockLobsterTrapClient``
      until the real Veea HTTP client lands)
    - Future: ``MicrosoftAgtClient``, ``BedrockAgentCoreClient``, ...
    """

    @abstractmethod
    async def evaluate(self, tenant_id: UUID, action: dict[str, Any]) -> PolicyVerdict:
        """Return a verdict for the given action.

        Implementations may retry transient errors internally; surface only
        terminal failures via ``PolicyEnforcementError``.
        """


__all__ = [
    "PolicyDecision",
    "PolicyEnforcementClient",
    "PolicyEnforcementError",
    "PolicyVerdict",
]

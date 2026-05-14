"""Policy enforcement + replay surface for Forensa.

The canonical vendor-neutral abstraction lives in
``packages.policy.enforcement``:

- ``PolicyDecision`` (enum)
- ``PolicyVerdict`` (dataclass)
- ``PolicyEnforcementClient`` (ABC)
- ``PolicyEnforcementError`` (exception)

Concrete adapters live in vendor-specific modules:

- ``packages.policy.lobstertrap`` -> ``VeeaLobsterTrapClient`` +
  ``MockLobsterTrapClient`` (Veea Lobster Trap)

The lobstertrap module also re-exports the canonical names under their
legacy aliases (``LobsterTrapClient`` / ``LobsterTrapError``) so existing
callers continue to work without changes.
"""

from packages.policy.enforcement import (
    PolicyDecision,
    PolicyEnforcementClient,
    PolicyEnforcementError,
    PolicyVerdict,
)

__all__ = [
    "PolicyDecision",
    "PolicyEnforcementClient",
    "PolicyEnforcementError",
    "PolicyVerdict",
]

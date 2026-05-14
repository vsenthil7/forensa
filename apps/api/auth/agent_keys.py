"""apps.api.auth.agent_keys — Agent Ed25519 signing key resolution.

CP9.18b / BR-02. Re-exports the agent signing key abstractions from
``apps.api.ingest_service`` so all the agent-identity primitives import
under one auth namespace::

    from apps.api.auth.agent_keys import (
        AgentSigningKeyProvider,
        InMemoryAgentSigningKeyProvider,
    )

instead of the legacy ingest_service import. The legacy import path
continues to work for backwards-compat with code written before CP9.18b
(``apps/api/routes/events.py`` predates this module).

Production cutover (CP11.1) replaces the in-memory provider with a KMS
adapter (AWS KMS / GCP KMS / HashiCorp Vault). The ABC stays at this
namespace; only the concrete impl moves.
"""

from __future__ import annotations

from apps.api.ingest_service import (
    AgentSigningKeyProvider,
    InMemoryAgentSigningKeyProvider,
)

__all__ = [
    "AgentSigningKeyProvider",
    "InMemoryAgentSigningKeyProvider",
]

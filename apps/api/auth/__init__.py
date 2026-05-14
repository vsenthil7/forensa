"""apps.api.auth — Forensa API authentication + principal resolution.

CP9.18b / BR-02 (Multi-party identity binding). This package provides:

- ``Principal``: the frozen resolved-from-token identity (tenant_id,
  agent_id, agent_slug, scopes).
- ``TokenVerifier`` / ``HmacBearerTokenVerifier``: Bearer-token verification.
- ``AgentSigningKeyProvider`` (re-exported from ingest_service): resolves
  the agent's Ed25519 signing key for the dual-signature receipt path.
- ``get_principal`` / ``get_token_verifier`` (in ``dependencies``): FastAPI
  Depends-callables that routes use to enforce authentication.

CP9.18c will wire ``Depends(get_principal)`` into every mutating + reading
route so that the API is no longer un-authenticated. Today (CP9.18b) the
auth layer EXISTS but is not yet enforced by the routes.

Production cutover to OIDC / JWT lands in CP10.1 with a JWKS-aware
``TokenVerifier`` implementation. The Principal contract stays stable.
"""

from __future__ import annotations

from apps.api.auth.agent_keys import (
    AgentSigningKeyProvider,
    InMemoryAgentSigningKeyProvider,
)
from apps.api.auth.dependencies import get_principal, get_token_verifier
from apps.api.auth.principal import Principal
from apps.api.auth.token import (
    ExpiredTokenError,
    HmacBearerTokenVerifier,
    InvalidTokenError,
    TokenVerifier,
    mint_hmac_token,
)

__all__ = [
    "AgentSigningKeyProvider",
    "ExpiredTokenError",
    "HmacBearerTokenVerifier",
    "InMemoryAgentSigningKeyProvider",
    "InvalidTokenError",
    "Principal",
    "TokenVerifier",
    "get_principal",
    "get_token_verifier",
    "mint_hmac_token",
]

"""apps.api.auth.dependencies — FastAPI dependencies for auth + principal resolution.

CP9.18b / BR-02. Provides the ``get_principal`` Depends-callable that
routes will use to:

1. Read the ``Authorization: Bearer <token>`` header.
2. Resolve the token to a ``Principal`` via a configured ``TokenVerifier``.
3. Raise HTTP 401 (with stable error codes) on any verification failure.

The verifier itself is wired via a separate ``get_token_verifier``
Depends-callable so tests can ``app.dependency_overrides`` it with a fake
that recognises pre-minted test tokens. Production wires a real
``HmacBearerTokenVerifier`` with the per-tenant secret loaded from
KMS (CP11.1) or env (today).

The route layer should depend on ``get_principal`` ONLY. The two-layer
indirection (verifier as a Depends, principal as a Depends) means
production can swap one without churning every route.

CP10.1 will replace this with an OIDC-aware version that pulls
``aud``/``iss``/``jwks_uri`` from a JWKS endpoint. The dependency
contract (``get_principal -> Principal``) stays stable.
"""

from __future__ import annotations

import logging
import os
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from apps.api.auth.principal import Principal
from apps.api.auth.token import (
    ExpiredTokenError,
    HmacBearerTokenVerifier,
    InvalidTokenError,
    TokenVerifier,
)

logger = logging.getLogger(__name__)

__all__ = [
    "get_principal",
    "get_token_verifier",
]


_DEFAULT_VERIFIER_HOLDER: dict[str, TokenVerifier | None] = {"verifier": None}


def _get_or_build_default_verifier() -> TokenVerifier | None:
    """Construct the default HMAC verifier from env once and cache it.

    Reads ``FORENSA_HMAC_SECRET`` (hex-encoded, at least 64 hex chars = 32
    bytes) and ``FORENSA_HMAC_TENANT_ID`` (UUID string). If either is
    missing or invalid, returns ``None`` and the route layer treats this
    as "auth not configured" (HTTP 503-equivalent).

    This factory runs at FIRST request, not at import time, so unit tests
    that ``app.dependency_overrides[get_token_verifier]`` are not forced
    to set the env vars.
    """
    cached = _DEFAULT_VERIFIER_HOLDER["verifier"]
    if cached is not None:
        return cached

    secret_hex = os.environ.get("FORENSA_HMAC_SECRET")
    tenant_id_str = os.environ.get("FORENSA_HMAC_TENANT_ID")
    if not secret_hex or not tenant_id_str:
        return None

    try:
        secret = bytes.fromhex(secret_hex)
    except ValueError:
        logger.error("forensa.auth.invalid_secret_hex")
        return None

    try:
        from uuid import UUID

        tenant_id = UUID(tenant_id_str)
    except ValueError:
        logger.error("forensa.auth.invalid_tenant_id_env")
        return None

    try:
        verifier = HmacBearerTokenVerifier(tenant_id=tenant_id, secret=secret)
    except ValueError:
        logger.error("forensa.auth.weak_secret")
        return None

    _DEFAULT_VERIFIER_HOLDER["verifier"] = verifier
    return verifier


async def get_token_verifier() -> TokenVerifier:
    """Default token verifier dependency. Override in tests.

    Production wires this from env via ``_get_or_build_default_verifier``.
    Tests inject a fake via ``app.dependency_overrides[get_token_verifier]``.

    Raises HTTP 503 if the production verifier cannot be constructed (env
    not set, weak secret, malformed UUID). This is intentional: a
    misconfigured auth layer should fail loudly, not silently fall back
    to anonymous access.
    """
    verifier = _get_or_build_default_verifier()
    if verifier is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "auth_not_configured",
                "reason": (
                    "FORENSA_HMAC_SECRET / FORENSA_HMAC_TENANT_ID env vars "
                    "are missing, malformed, or below the minimum strength"
                ),
            },
        )
    return verifier


async def get_principal(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    verifier: TokenVerifier = Depends(get_token_verifier),  # noqa: B008
) -> Principal:
    """Resolve the Authorization header to a ``Principal``.

    Routes depend on this directly::

        @router.post(...)
        async def submit_event(
            event: Event,
            principal: Principal = Depends(get_principal),
            ...
        ):
            if event.tenant_id != principal.tenant_id:
                raise HTTPException(403, "tenant mismatch")

    Failure modes (all return HTTP 401 with differentiated error codes
    in ``detail.error``):

    - ``auth_required``: no Authorization header at all.
    - ``token_invalid``: header doesn't say ``Bearer <token>``, or the token
      fails MAC / claim-shape checks.
    - ``token_expired``: MAC verifies but ``exp`` is past.
    """
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "auth_required", "reason": "Authorization header required"},
        )

    # Expected shape: "Bearer <token>" (case-insensitive on Bearer per
    # RFC 6750 §2.1, though we accept it as written - production OIDC
    # clients always emit "Bearer ").
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "token_invalid",
                "reason": "Authorization header must be 'Bearer <token>'",
            },
        )
    token = parts[1].strip()

    try:
        principal = verifier.verify(token)
    except ExpiredTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "token_expired", "reason": str(exc)},
        ) from exc
    except InvalidTokenError as exc:
        # Generic message - do NOT leak which check failed.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "token_invalid", "reason": "invalid token"},
        ) from exc

    return principal

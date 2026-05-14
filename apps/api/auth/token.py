"""apps.api.auth.token — Bearer token verification for the Forensa API.

CP9.18b / BR-02. Provides:

- ``TokenVerifier`` ABC: ``verify(token: str) -> Principal`` (raises on bad token).
- ``HmacBearerTokenVerifier``: a concrete impl using a per-tenant shared
  secret + HMAC-SHA256 over a JSON payload. The token format is::

      base64url(payload_json).base64url(hmac_sha256(payload_json, secret))

  Cheap, deterministic, no external dependencies. Suitable for the
  hackathon-week design-partner demo. Production cutover to OIDC / signed
  JWT lands in CP10.1 with the auth infrastructure refactor.

- ``mint_hmac_token`` test helper: produces a signed token for a given
  Principal so tests don't reach into the internals.

- Exception classes for downstream HTTP mapping:
  ``InvalidTokenError`` (unparseable / bad-MAC / claim-shape wrong) and
  ``ExpiredTokenError`` (signature OK but ``exp`` past).

Security notes
--------------

- The MAC compare uses ``hmac.compare_digest`` (constant time). Naive
  ``a == b`` on bytes is timing-vulnerable; a network attacker can exfiltrate
  the secret byte-by-byte from response timing if compare is not
  constant-time.
- Tokens carry only opaque identifiers (tenant_id, agent_id, agent_slug,
  scopes, optional exp). They do NOT carry the agent's signing key. The
  signing key resolution is a separate concern in
  ``AgentSigningKeyProvider``.
- The payload is base64url-encoded but NOT encrypted. Anyone with the token
  can read its contents. That is fine for v1; in CP10.1 OIDC/JWT-encrypted
  variant lands.
- Token reuse across tenants is impossible because each verifier is
  configured with one tenant's secret. The verifier rejects tokens whose
  payload tenant_id does not match the configured one. (CP10.1: per-issuer
  JWKS replaces this with proper key rotation.)
"""

from __future__ import annotations

import base64
import binascii
import hmac
import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from apps.api.auth.principal import Principal

__all__ = [
    "ExpiredTokenError",
    "HmacBearerTokenVerifier",
    "InvalidTokenError",
    "TokenVerifier",
    "mint_hmac_token",
]


class InvalidTokenError(Exception):
    """The token is unparseable, malformed, or its MAC does not verify.

    The route layer maps this to HTTP 401 Unauthorized. The reason string
    is intentionally generic ("invalid token") to avoid leaking which
    specific check failed - same security posture as bcrypt/argon2's
    deliberate vagueness around "user not found" vs "wrong password".
    """


class ExpiredTokenError(Exception):
    """Token MAC is valid but the ``exp`` claim is in the past.

    Distinct from ``InvalidTokenError`` so the route layer can return a
    differentiated error code (eg ``token_expired`` vs ``token_invalid``)
    that a refresh-aware client can act on without prompting the user to
    re-authenticate.
    """


class TokenVerifier(ABC):
    """Verifies a Bearer token and resolves it to a ``Principal``.

    Production-wired in ``apps.api.auth.dependencies.get_principal``
    (CP9.18c). Tests inject a fake via ``app.dependency_overrides``.
    """

    @abstractmethod
    def verify(self, token: str) -> Principal:
        """Verify ``token`` and return the resolved ``Principal``.

        Raises ``InvalidTokenError`` on any verification failure.
        Raises ``ExpiredTokenError`` if MAC is valid but ``exp`` is past.
        """


def _b64url_encode(data: bytes) -> str:
    """Base64url-encode without padding (=). RFC 4648 §5."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    """Decode base64url, restoring the padding the encoder stripped."""
    padding = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + padding)


class HmacBearerTokenVerifier(TokenVerifier):
    """Verify Bearer tokens of the form ``b64u(payload).b64u(mac)``.

    Parameters
    ----------
    tenant_id : UUID
        The single tenant this verifier accepts tokens for. Tokens whose
        payload ``tenant_id`` does not match are rejected. (One verifier
        per tenant means a leaked secret cannot impersonate other tenants.)
    secret : bytes
        The HMAC-SHA256 secret. Must be at least 32 bytes to be considered
        cryptographically adequate. The constructor enforces this.
    """

    _MIN_SECRET_LEN: int = 32

    def __init__(self, *, tenant_id: UUID, secret: bytes) -> None:
        if len(secret) < self._MIN_SECRET_LEN:
            raise ValueError(
                f"HMAC secret must be at least {self._MIN_SECRET_LEN} bytes "
                f"(got {len(secret)} bytes); refusing weak-secret configuration"
            )
        self._tenant_id = tenant_id
        self._secret = secret

    def verify(self, token: str) -> Principal:
        # Split must be exact: payload "." mac. Anything else is malformed.
        parts = token.split(".")
        if len(parts) != 2:
            raise InvalidTokenError("token shape must be 'payload.mac'")

        payload_b64, mac_b64 = parts
        try:
            payload_bytes = _b64url_decode(payload_b64)
            received_mac = _b64url_decode(mac_b64)
        except (ValueError, binascii.Error) as exc:
            raise InvalidTokenError("token base64url decode failed") from exc

        expected_mac = hmac.new(self._secret, payload_bytes, sha256).digest()
        # CRITICAL: constant-time compare to avoid timing side-channel.
        if not hmac.compare_digest(received_mac, expected_mac):
            raise InvalidTokenError("token MAC verification failed")

        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InvalidTokenError("token payload is not valid JSON") from exc

        if not isinstance(payload, dict):
            raise InvalidTokenError("token payload must be a JSON object")

        # Required claims: tenant_id, agent_id, agent_slug.
        try:
            payload_tenant_id = UUID(payload["tenant_id"])
            agent_id = UUID(payload["agent_id"])
            agent_slug = payload["agent_slug"]
        except (KeyError, ValueError, TypeError) as exc:
            raise InvalidTokenError("token payload missing required claim") from exc

        if not isinstance(agent_slug, str) or not agent_slug:
            raise InvalidTokenError("token payload agent_slug must be non-empty str")

        # Tenant-scoping: refuse tokens for other tenants. A per-tenant
        # verifier rejects cross-tenant tokens at the secret layer (no
        # matching secret) but if a secret leaks between two tenants,
        # this check is the second wall.
        if payload_tenant_id != self._tenant_id:
            raise InvalidTokenError("token tenant_id does not match verifier")

        # Optional scopes claim; defaults to empty if absent.
        scopes_raw = payload.get("scopes", [])
        if not isinstance(scopes_raw, list) or not all(isinstance(s, str) for s in scopes_raw):
            raise InvalidTokenError("token scopes must be a list of strings")
        scopes = frozenset(scopes_raw)

        # Optional exp claim; if present, must be a UNIX timestamp (int or
        # float seconds) and in the future.
        exp_raw = payload.get("exp")
        if exp_raw is not None:
            if not isinstance(exp_raw, int | float):
                raise InvalidTokenError("token exp must be a number (UNIX seconds)")
            now_ts = datetime.now(UTC).timestamp()
            if exp_raw < now_ts:
                raise ExpiredTokenError(f"token expired at {exp_raw} (now {now_ts:.0f})")

        return Principal(
            tenant_id=payload_tenant_id,
            agent_id=agent_id,
            agent_slug=agent_slug,
            scopes=scopes,
        )


def mint_hmac_token(
    *,
    tenant_id: UUID,
    agent_id: UUID,
    agent_slug: str,
    secret: bytes,
    scopes: list[str] | None = None,
    exp: float | None = None,
) -> str:
    """Mint a Bearer token verifiable by ``HmacBearerTokenVerifier``.

    Test helper + service-account issuance primitive. Production token
    issuance (CP10.1) replaces this with a signed JWT minted by the auth
    service; this function is the transitional shape.

    Parameters
    ----------
    tenant_id, agent_id, agent_slug
        Required claims that become Principal fields.
    secret
        The HMAC secret for this tenant. Must match the verifier's secret.
    scopes
        Optional list of opaque scope strings.
    exp
        Optional UNIX-seconds expiry timestamp. Tokens without an exp do
        NOT expire under HMAC verification (CP10.1 switches to OIDC short-
        TTL access tokens + refresh tokens).

    Returns
    -------
    str
        The ``payload.mac`` token suitable for an ``Authorization: Bearer``
        header.
    """
    if len(secret) < HmacBearerTokenVerifier._MIN_SECRET_LEN:
        raise ValueError(
            "HMAC secret must be at least " f"{HmacBearerTokenVerifier._MIN_SECRET_LEN} bytes"
        )

    payload: dict[str, object] = {
        "tenant_id": str(tenant_id),
        "agent_id": str(agent_id),
        "agent_slug": agent_slug,
        "scopes": list(scopes) if scopes is not None else [],
    }
    if exp is not None:
        payload["exp"] = exp

    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    mac = hmac.new(secret, payload_bytes, sha256).digest()
    return f"{_b64url_encode(payload_bytes)}.{_b64url_encode(mac)}"

# apps/api/auth — Forensa API authentication + principal resolution

CP9.18b / BR-02 (Multi-party identity binding). Provides bearer-token
verification, principal resolution, and agent signing key abstractions.

## Modules

- `principal.py` — `Principal` frozen dataclass: `(tenant_id, agent_id, agent_slug, scopes)`. Pure data.
- `token.py` — `TokenVerifier` ABC + `HmacBearerTokenVerifier` (HMAC-SHA256 over a JSON payload). Constant-time MAC compare. Optional `exp` claim. `mint_hmac_token` test helper.
- `agent_keys.py` — re-exports `AgentSigningKeyProvider` + `InMemoryAgentSigningKeyProvider` from `apps.api.ingest_service` for symmetric importing.
- `dependencies.py` — `get_principal` / `get_token_verifier` FastAPI Depends-callables. Maps token failures to HTTP 401 with differentiated error codes (`auth_required`, `token_invalid`, `token_expired`).

## Token shape (HMAC variant)

```
base64url(payload_json).base64url(hmac_sha256(payload_json, secret))
```

Payload JSON keys: `tenant_id` (UUID str), `agent_id` (UUID str), `agent_slug` (str), `scopes` (list[str], optional), `exp` (UNIX seconds, optional).

## Env vars (default verifier)

- `FORENSA_HMAC_SECRET` — hex-encoded HMAC secret, at least 64 hex chars (32 bytes).
- `FORENSA_HMAC_TENANT_ID` — UUID string this verifier accepts tokens for.

If either is missing or malformed, `get_token_verifier` returns HTTP 503 `auth_not_configured`. The auth layer fails loudly rather than silently allowing anonymous access.

## What lands when

| CP | Scope |
|---|---|
| CP9.18b (this commit) | Auth module exists. NOT yet wired into routes. |
| CP9.18c (next) | `Depends(get_principal)` wired into events/receipts/evidence/narratives routes. Tenant + agent_id mismatch returns 403. |
| CP10.1 | OIDC / JWT verifier replaces HMAC. JWKS-aware. Principal contract stays stable. |
| CP11.1 | KMS-backed signing keys replace `InMemoryAgentSigningKeyProvider`. |

## Test seam

Tests inject a fake verifier via `app.dependency_overrides[get_token_verifier]` to avoid having to set the env vars at module import. The `mint_hmac_token` helper produces tokens that the default verifier accepts when the test harness configures matching secret + tenant_id.

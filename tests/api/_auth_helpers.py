"""Shared test helper: install a Principal override on a FastAPI app (CP9.18c).

CP9.18c wires ``Depends(get_principal)`` into every route. Every existing
route test that doesn't mint a real HMAC token would 401 - which is the
point of the new auth layer but useless for the test's actual goal
(verifying business logic with pre-built fixtures).

Tests use this module's ``install_principal_override`` to short-circuit
the auth resolution and inject a known-good ``Principal`` for the
duration of the test::

    from tests.api._auth_helpers import install_principal_override

    @pytest.fixture
    def app(_TENANT_ID, _AGENT_ID):
        a = create_app()
        install_principal_override(a, tenant_id=_TENANT_ID, agent_id=_AGENT_ID)
        return a

The override is scoped to the test app instance. It does NOT touch the
default ``get_token_verifier`` env-driven path - that remains the
production code path that real tokens flow through.

A separate cluster of tests in ``test_routes_auth_enforcement.py`` (added
in CP9.18c) verifies the unauthenticated 401 and tenant-mismatch 403
behaviour by EXPLICITLY NOT installing this override.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI

from apps.api.auth.dependencies import get_principal
from apps.api.auth.principal import Principal


def install_principal_override(
    app: FastAPI,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    agent_slug: str = "test-agent",
    scopes: frozenset[str] | None = None,
) -> Principal:
    """Override ``get_principal`` on ``app`` to return a fixture Principal.

    Returns the installed Principal so tests can assert on it if needed.

    Idempotent: calling twice replaces the previous override.
    """
    principal = Principal(
        tenant_id=tenant_id,
        agent_id=agent_id,
        agent_slug=agent_slug,
        scopes=scopes if scopes is not None else frozenset(),
    )

    async def _override() -> Principal:
        return principal

    app.dependency_overrides[get_principal] = _override
    return principal

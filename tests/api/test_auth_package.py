"""Tests for apps.api.auth.agent_keys + apps.api.auth.__init__ re-exports.

CP9.18b. These tests are tiny but important: they confirm that the auth
package surface (the __all__ in __init__.py) is intact and that
``agent_keys`` re-exports the existing ingest_service ABCs without
introducing a divergent definition.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from apps.api import auth as auth_pkg
from apps.api.auth.agent_keys import (
    AgentSigningKeyProvider,
    InMemoryAgentSigningKeyProvider,
)
from apps.api.ingest_service import (
    AgentSigningKeyProvider as _IngestAgentSigningKeyProvider,
)
from apps.api.ingest_service import (
    InMemoryAgentSigningKeyProvider as _IngestInMemoryAgentSigningKeyProvider,
)


def test_agent_keys_reexports_are_identical_to_ingest_service():
    """agent_keys.AgentSigningKeyProvider IS ingest_service.AgentSigningKeyProvider.

    Re-export, not redefinition. A divergent definition would silently break
    isinstance() checks and dependency-injection equivalence.
    """
    assert AgentSigningKeyProvider is _IngestAgentSigningKeyProvider
    assert InMemoryAgentSigningKeyProvider is _IngestInMemoryAgentSigningKeyProvider


@pytest.mark.asyncio
async def test_in_memory_agent_signing_key_provider_still_works_via_auth_reexport():
    """Importing via the auth namespace must produce a working provider."""
    p = InMemoryAgentSigningKeyProvider()
    key = await p.get_signing_key(uuid4())
    assert len(key) == 32


def test_auth_package_all_exports_resolve():
    """Every name listed in apps.api.auth.__all__ must be importable from the
    package namespace."""
    for name in auth_pkg.__all__:
        assert hasattr(auth_pkg, name), f"missing export: {name}"


def test_auth_package_exports_principal():
    assert hasattr(auth_pkg, "Principal")
    p = auth_pkg.Principal(tenant_id=uuid4(), agent_id=uuid4(), agent_slug="x")
    assert p.tenant_id is not None


def test_auth_package_exports_token_classes():
    assert hasattr(auth_pkg, "HmacBearerTokenVerifier")
    assert hasattr(auth_pkg, "TokenVerifier")
    assert hasattr(auth_pkg, "InvalidTokenError")
    assert hasattr(auth_pkg, "ExpiredTokenError")
    assert hasattr(auth_pkg, "mint_hmac_token")


def test_auth_package_exports_dependencies():
    assert hasattr(auth_pkg, "get_principal")
    assert hasattr(auth_pkg, "get_token_verifier")

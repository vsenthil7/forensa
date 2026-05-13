"""Tests for Tenant schema model."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from packages.schema.tenant import Tenant


def test_tenant_minimal_valid_construction():
    t = Tenant(slug="acme-emea", display_name="Acme EMEA", signing_key_id="key-1")
    assert t.slug == "acme-emea"
    assert t.display_name == "Acme EMEA"
    assert t.signing_key_id == "key-1"
    assert t.id is not None
    assert t.created_at.tzinfo is not None


def test_tenant_explicit_uuid_and_timestamp():
    tid = uuid4()
    ts = datetime(2026, 5, 13, 8, 0, tzinfo=UTC)
    t = Tenant(id=tid, slug="acme", display_name="X", signing_key_id="k", created_at=ts)
    assert t.id == tid
    assert t.created_at == ts


def test_tenant_as_identity_helper():
    t = Tenant(slug="acme-emea", display_name="Acme EMEA", signing_key_id="key-1")
    assert t.as_identity() == "tenant:acme-emea"


@pytest.mark.parametrize(
    "bad_slug",
    ["AB", "a", "a" * 64, "-acme", "acme-", "ac me", "acme_emea"],
)
def test_tenant_rejects_invalid_slug(bad_slug):
    with pytest.raises(ValidationError):
        Tenant(slug=bad_slug, display_name="X", signing_key_id="k")


def test_tenant_rejects_naive_created_at():
    with pytest.raises(ValidationError) as exc_info:
        Tenant(
            slug="acme",
            display_name="X",
            signing_key_id="k",
            created_at=datetime(2026, 5, 13, 8, 0),
        )
    assert "timezone-aware" in str(exc_info.value)


def test_tenant_frozen():
    t = Tenant(slug="acme", display_name="X", signing_key_id="k")
    with pytest.raises(ValidationError):
        t.slug = "other"


def test_tenant_forbids_extra_fields():
    with pytest.raises(ValidationError):
        Tenant(slug="acme", display_name="X", signing_key_id="k", evil="data")

"""Tests for PolicyBundle schema model — 100% branch coverage."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from packages.schema.policy_bundle import PolicyBundle

_GOOD_HASH = "a" * 64


def _good(**over):
    base = dict(
        tenant_id=uuid4(),
        version="1.2.3",
        content_hash=_GOOD_HASH,
        content={"rules": [{"id": "r1", "effect": "allow"}]},
    )
    base.update(over)
    return base


def test_policy_bundle_minimal_valid():
    pb = PolicyBundle(**_good())
    assert pb.version == "1.2.3"
    assert pb.content_hash == _GOOD_HASH
    assert pb.content["rules"][0]["id"] == "r1"
    assert pb.created_at.tzinfo is not None


@pytest.mark.parametrize("version", ["1", "1.2", "1.2.3", "10.20.30", "0", "0.0.1"])
def test_policy_bundle_accepts_valid_version(version):
    pb = PolicyBundle(**_good(version=version))
    assert pb.version == version


@pytest.mark.parametrize(
    "bad_version",
    ["", "v1.2.3", "1.2.x", "1..2", ".1.2", "1.2.", "abc", "1-2-3"],
)
def test_policy_bundle_rejects_invalid_version(bad_version):
    with pytest.raises(ValidationError):
        PolicyBundle(**_good(version=bad_version))


@pytest.mark.parametrize(
    "bad_hash",
    ["", "a" * 63, "a" * 65, "A" * 64, "g" * 64, "z" * 64, "0" * 63 + "!"],
)
def test_policy_bundle_rejects_bad_content_hash(bad_hash):
    with pytest.raises(ValidationError) as exc:
        PolicyBundle(**_good(content_hash=bad_hash))
    assert "64-char" in str(exc.value) or "SHA-256" in str(exc.value)


def test_policy_bundle_explicit_id_and_created_at():
    pid = uuid4()
    ts = datetime(2026, 5, 13, 8, 0, tzinfo=UTC)
    pb = PolicyBundle(id=pid, created_at=ts, **_good())
    assert pb.id == pid
    assert pb.created_at == ts


def test_policy_bundle_rejects_naive_created_at():
    with pytest.raises(ValidationError) as exc:
        PolicyBundle(created_at=datetime(2026, 5, 13, 8, 0), **_good())
    assert "timezone-aware" in str(exc.value)


def test_policy_bundle_frozen():
    pb = PolicyBundle(**_good())
    with pytest.raises(ValidationError):
        pb.version = "9.9.9"


def test_policy_bundle_forbids_extra_fields():
    with pytest.raises(ValidationError):
        PolicyBundle(evil="data", **_good())


def test_policy_bundle_complex_content_accepted():
    complex_content = {
        "rules": [
            {"id": "r1", "match": {"tool": "search"}, "effect": "allow"},
            {"id": "r2", "match": {"resource": "/admin/*"}, "effect": "deny"},
        ],
        "metadata": {"author": "compliance-team", "approved": True},
    }
    pb = PolicyBundle(**_good(content=complex_content))
    assert len(pb.content["rules"]) == 2

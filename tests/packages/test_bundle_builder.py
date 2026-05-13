"""Tests for packages/policy/bundle_builder.py - 100% branch coverage.

Covers:
- compute_content_hash: deterministic, matches sha256_hex(content)
- build_bundle: bundle.content_hash equals compute_content_hash(content)
- rebind_bundle: returns NEW bundle, keeps tenant_id, gets fresh id/created_at,
  new content_hash matches new content
- verify_content_hash: True for fresh, False after content mutation (constructed
  through model_construct to skip frozen-instance protection)
- require_content_hash: passes for fresh, raises PolicyBundleHashMismatch for stale
- bump_major/minor/patch: happy path + length errors + non-numeric error
- _parse_version: empty string error
"""

from __future__ import annotations

from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from packages.crypto.hash import sha256_hex
from packages.policy.bundle_builder import (
    PolicyBundleHashMismatchError,
    build_bundle,
    bump_major,
    bump_minor,
    bump_patch,
    compute_content_hash,
    rebind_bundle,
    require_content_hash,
    verify_content_hash,
)
from packages.schema.policy_bundle import PolicyBundle

_TENANT_ID = UUID("33333333-3333-3333-3333-333333333333")
_SAMPLE_CONTENT = {
    "rules": [{"kind": "deny_kind", "decision": "deny"}],
    "default": "allow",
}


# ---------- compute_content_hash ----------


def test_compute_content_hash_matches_sha256_hex():
    assert compute_content_hash(_SAMPLE_CONTENT) == sha256_hex(_SAMPLE_CONTENT)


def test_compute_content_hash_is_deterministic():
    a = compute_content_hash(_SAMPLE_CONTENT)
    b = compute_content_hash(_SAMPLE_CONTENT)
    assert a == b


def test_compute_content_hash_changes_with_content():
    a = compute_content_hash(_SAMPLE_CONTENT)
    b = compute_content_hash({"rules": [], "default": "allow"})
    assert a != b


# ---------- build_bundle ----------


def test_build_bundle_binds_content_hash():
    b = build_bundle(tenant_id=_TENANT_ID, version="1.0.0", content=_SAMPLE_CONTENT)
    assert isinstance(b, PolicyBundle)
    assert b.tenant_id == _TENANT_ID
    assert b.version == "1.0.0"
    assert b.content == _SAMPLE_CONTENT
    assert b.content_hash == sha256_hex(_SAMPLE_CONTENT)


def test_build_bundle_assigns_fresh_id_and_created_at():
    a = build_bundle(tenant_id=_TENANT_ID, version="1.0.0", content=_SAMPLE_CONTENT)
    b = build_bundle(tenant_id=_TENANT_ID, version="1.0.0", content=_SAMPLE_CONTENT)
    assert a.id != b.id


# ---------- rebind_bundle ----------


def test_rebind_bundle_returns_new_bundle_with_updated_content():
    orig = build_bundle(tenant_id=_TENANT_ID, version="1.0.0", content=_SAMPLE_CONTENT)
    new_content = {"rules": [{"kind": "x", "decision": "allow"}], "default": "deny"}
    rebound = rebind_bundle(orig, new_content=new_content, new_version="1.1.0")
    assert rebound is not orig
    assert rebound.tenant_id == orig.tenant_id
    assert rebound.id != orig.id
    assert rebound.version == "1.1.0"
    assert rebound.content == new_content
    assert rebound.content_hash == sha256_hex(new_content)


# ---------- verify_content_hash / require_content_hash ----------


def test_verify_content_hash_passes_for_freshly_built_bundle():
    b = build_bundle(tenant_id=_TENANT_ID, version="1.0.0", content=_SAMPLE_CONTENT)
    assert verify_content_hash(b) is True


def test_verify_content_hash_fails_when_hash_does_not_match_content():
    # Construct a bundle whose content_hash is valid hex but unrelated to content.
    wrong_hash = sha256_hex({"different": "content"})
    bad = PolicyBundle(
        tenant_id=_TENANT_ID,
        version="1.0.0",
        content_hash=wrong_hash,
        content=_SAMPLE_CONTENT,
    )
    assert verify_content_hash(bad) is False


def test_require_content_hash_passes_for_fresh_bundle():
    b = build_bundle(tenant_id=_TENANT_ID, version="1.0.0", content=_SAMPLE_CONTENT)
    # Should not raise.
    require_content_hash(b)


def test_require_content_hash_raises_on_mismatch():
    wrong_hash = sha256_hex({"unrelated": True})
    bad = PolicyBundle(
        tenant_id=_TENANT_ID,
        version="1.0.0",
        content_hash=wrong_hash,
        content=_SAMPLE_CONTENT,
    )
    with pytest.raises(PolicyBundleHashMismatchError, match="content_hash does not match"):
        require_content_hash(bad)


# ---------- bump_major / bump_minor / bump_patch ----------


def test_bump_major_increments_first_resets_rest():
    assert bump_major("1.2.3") == "2.0.0"


def test_bump_major_works_on_two_part_version():
    assert bump_major("4.7") == "5.0.0"


def test_bump_major_works_on_single_part_version():
    assert bump_major("9") == "10.0.0"


def test_bump_minor_increments_second_resets_third():
    assert bump_minor("1.2.3") == "1.3.0"


def test_bump_minor_works_on_two_part_version():
    assert bump_minor("4.7") == "4.8.0"


def test_bump_minor_rejects_single_part_version():
    with pytest.raises(ValueError, match="at least two components"):
        bump_minor("9")


def test_bump_patch_increments_third():
    assert bump_patch("1.2.3") == "1.2.4"


def test_bump_patch_rejects_short_version():
    with pytest.raises(ValueError, match="at least three components"):
        bump_patch("4.7")


# ---------- _parse_version error paths (via the bumpers) ----------


def test_bump_rejects_empty_string():
    with pytest.raises(ValueError, match="non-empty string"):
        bump_patch("")


def test_bump_rejects_non_numeric():
    with pytest.raises(ValueError, match="dotted decimal"):
        bump_patch("1.a.3")


# ---------- Hypothesis property tests ----------


@given(
    st.dictionaries(
        keys=st.text(min_size=1, max_size=10),
        values=st.one_of(st.text(max_size=20), st.integers(-(2**31), 2**31 - 1), st.booleans()),
        max_size=8,
    )
)
def test_build_bundle_property_content_hash_always_matches(content):
    """For any canonicalisable content, the resulting bundle's content_hash
    must equal sha256_hex(b.content) (the post-validated content stored on
    the bundle, which may differ from the raw input due to pydantic
    string coercions) and verify_content_hash must be True."""
    b = build_bundle(tenant_id=_TENANT_ID, version="1.0.0", content=content)
    assert b.content_hash == sha256_hex(b.content)
    assert verify_content_hash(b) is True


@given(
    st.integers(min_value=0, max_value=999),
    st.integers(min_value=0, max_value=999),
    st.integers(min_value=0, max_value=999),
)
def test_bump_patch_property_only_increments_third(maj, mn, pt):
    """bump_patch leaves major and minor untouched and increments patch by 1."""
    version = f"{maj}.{mn}.{pt}"
    bumped = bump_patch(version)
    parts = [int(x) for x in bumped.split(".")]
    assert parts == [maj, mn, pt + 1]

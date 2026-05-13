"""PolicyBundle builder that binds content_hash deterministically from content.

The PolicyBundle schema (packages/schema/policy_bundle.py) accepts any
content_hash that matches the SHA-256 hex shape. This module provides the
canonical way to produce one: compute it from canonical_json(content).

Why a separate module:
- Keeps the schema pure (validates shape only, no crypto dependency).
- Centralises the content -> hash binding so every code path that creates a
  bundle does it the same way. A bundle whose content_hash does not equal
  sha256_hex(content) is malformed and rejected here.
- Provides build_bundle() for new bundles and rebind_bundle() for the
  immutable update pattern when content changes.

Versioning:
- Versions are dotted decimal (validated in the schema).
- bump_version() helpers for major/minor/patch increments; pure functions
  on the version string, no I/O.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from packages.crypto.hash import sha256_hex
from packages.schema.policy_bundle import PolicyBundle


class PolicyBundleHashMismatchError(ValueError):
    """Raised when a bundle's content_hash does not equal sha256_hex(content)."""


def compute_content_hash(content: dict[str, Any]) -> str:
    """Return the canonical SHA-256 hex of a policy-bundle content payload."""
    return sha256_hex(content)


def build_bundle(
    *,
    tenant_id: UUID,
    version: str,
    content: dict[str, Any],
) -> PolicyBundle:
    """Construct a PolicyBundle with content_hash computed from content.

    This is the only function callers should use to create new bundles.
    The hash is computed from the POST-VALIDATED content stored in the
    bundle (after any pydantic coercion such as whitespace stripping) so
    that verify_content_hash(bundle) is always True for freshly built
    bundles regardless of schema-level string coercions.
    """
    # Two-step build: first construct with a placeholder hash to let the
    # schema apply any string coercions, then rebind to the canonical hash.
    placeholder = "0" * 64
    draft = PolicyBundle(
        tenant_id=tenant_id,
        version=version,
        content_hash=placeholder,
        content=content,
    )
    final_hash = compute_content_hash(draft.content)
    return PolicyBundle(
        id=draft.id,
        tenant_id=draft.tenant_id,
        version=draft.version,
        content_hash=final_hash,
        content=draft.content,
        created_at=draft.created_at,
    )


def rebind_bundle(
    bundle: PolicyBundle,
    *,
    new_content: dict[str, Any],
    new_version: str,
) -> PolicyBundle:
    """Return a NEW PolicyBundle with updated content and recomputed hash.

    Bundles are frozen; this is the immutable-update entry point. The new
    bundle keeps the same tenant_id but receives a fresh id and a fresh
    created_at via PolicyBundle defaults. Hash is bound from the
    post-validated content (same two-step pattern as build_bundle).
    """
    return build_bundle(
        tenant_id=bundle.tenant_id,
        version=new_version,
        content=new_content,
    )


def verify_content_hash(bundle: PolicyBundle) -> bool:
    """Return True iff bundle.content_hash == sha256_hex(bundle.content)."""
    return bundle.content_hash == compute_content_hash(bundle.content)


def require_content_hash(bundle: PolicyBundle) -> None:
    """Raise PolicyBundleHashMismatch if the bundle's content_hash is stale.

    Use this at trust boundaries (e.g. loading a bundle from storage before
    binding a Receipt to it) to assert tamper-evidence.
    """
    if not verify_content_hash(bundle):
        raise PolicyBundleHashMismatchError(
            f"bundle {bundle.id} content_hash does not match sha256_hex(content)"
        )


def bump_major(version: str) -> str:
    """Return the next major version (X.Y.Z -> (X+1).0.0)."""
    parts = _parse_version(version)
    # _parse_version guarantees parts has at least one element; no need for a
    # secondary length check here.
    return _format_version([parts[0] + 1, 0, 0])


def bump_minor(version: str) -> str:
    """Return the next minor version (X.Y.Z -> X.(Y+1).0)."""
    parts = _parse_version(version)
    if len(parts) < 2:
        raise ValueError("version must have at least two components for minor bump")
    return _format_version([parts[0], parts[1] + 1, 0])


def bump_patch(version: str) -> str:
    """Return the next patch version (X.Y.Z -> X.Y.(Z+1))."""
    parts = _parse_version(version)
    if len(parts) < 3:
        raise ValueError("version must have at least three components for patch bump")
    return _format_version([parts[0], parts[1], parts[2] + 1])


def _parse_version(version: str) -> list[int]:
    if not version:
        raise ValueError("version must be a non-empty string")
    try:
        return [int(p) for p in version.split(".")]
    except ValueError as exc:
        raise ValueError(f"version must be dotted decimal, got {version!r}") from exc


def _format_version(parts: list[int]) -> str:
    return ".".join(str(p) for p in parts)

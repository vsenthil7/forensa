"""Canonical SHA-256 hashing for deterministic content-addressable identity.

Used as the building block for Receipt.payload_hash and the Merkle chain.

Canonicalisation rules:
- JSON objects: keys sorted, no whitespace (RFC 8785 JCS-lite).
- Bytes hashed directly.
- Strings encoded as UTF-8 then hashed.
- Datetimes encoded as ISO-8601 with explicit timezone.
- None is NOT a permissible input (would silently elide differences).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any


def canonical_json(payload: Any) -> bytes:
    """Return the canonical UTF-8 bytes of a JSON-serialisable payload.

    Datetimes are converted to ISO-8601 strings with timezone preserved.
    Sets are converted to sorted lists. Bytes are base64-encoded.
    """
    return json.dumps(
        _normalise(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _normalise(value: Any) -> Any:
    if value is None:
        raise ValueError("None is not a permissible canonical input")
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value.isoformat()
    if isinstance(value, bytes):
        import base64

        return "base64:" + base64.b64encode(value).decode("ascii")
    if isinstance(value, set | frozenset):
        return sorted(_normalise(v) for v in value)
    if isinstance(value, dict):
        return {str(k): _normalise(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_normalise(v) for v in value]
    if isinstance(value, str | int | float | bool):
        return value
    raise TypeError(f"unsupported type for canonicalisation: {type(value).__name__}")


def sha256_hex(payload: Any) -> str:
    """Return the lowercase hex SHA-256 of the canonicalised payload."""
    return hashlib.sha256(canonical_json(payload)).hexdigest()


def sha256_bytes(payload: Any) -> bytes:
    """Return the raw 32-byte SHA-256 digest of the canonicalised payload."""
    return hashlib.sha256(canonical_json(payload)).digest()

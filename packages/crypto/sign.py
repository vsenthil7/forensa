"""Ed25519 detached signatures over canonical JSON.

Used by the Receipt issuance pipeline to sign receipt_hash. Tenant key
material is stored separately; this module is pure crypto over bytes.

Contract:
- generate_keypair() returns (private_key_bytes, public_key_bytes) as
  32-byte raw seeds / 32-byte raw public keys.
- sign(private_key_bytes, payload) returns a 64-byte detached signature
  over canonical_json(payload).
- verify(public_key_bytes, payload, signature_bytes) returns True iff
  signature is valid; False on any verification failure (never raises).
- load_private_key / load_public_key parse raw byte forms with explicit
  length validation.

All signatures are produced over canonical_json(payload) bytes, so two
payloads that differ only in key ordering or whitespace yield the same
signature.
"""

from __future__ import annotations

from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from packages.crypto.hash import canonical_json

_PRIVATE_KEY_LEN = 32
_PUBLIC_KEY_LEN = 32
_SIGNATURE_LEN = 64


def generate_keypair() -> tuple[bytes, bytes]:
    """Generate a new Ed25519 keypair as raw byte seeds.

    Returns (private_key_bytes_32, public_key_bytes_32).
    """
    private_key = Ed25519PrivateKey.generate()
    return _serialise_private(private_key), _serialise_public(private_key.public_key())


def sign(private_key_bytes: bytes, payload: Any) -> bytes:
    """Sign canonical_json(payload) with the given raw Ed25519 private key.

    Returns a 64-byte detached signature.
    """
    key = load_private_key(private_key_bytes)
    return key.sign(canonical_json(payload))


def verify(public_key_bytes: bytes, payload: Any, signature_bytes: bytes) -> bool:
    """Verify a detached signature over canonical_json(payload).

    Returns True iff the signature is valid. Returns False on any verification
    failure (invalid signature, malformed key, wrong length). Never raises.
    """
    if len(signature_bytes) != _SIGNATURE_LEN:
        return False
    try:
        key = load_public_key(public_key_bytes)
    except ValueError:
        return False
    try:
        key.verify(signature_bytes, canonical_json(payload))
    except InvalidSignature:
        return False
    return True


def load_private_key(private_key_bytes: bytes) -> Ed25519PrivateKey:
    """Parse a 32-byte raw Ed25519 private key seed."""
    if not isinstance(private_key_bytes, bytes):
        raise TypeError("private_key_bytes must be bytes")
    if len(private_key_bytes) != _PRIVATE_KEY_LEN:
        raise ValueError(
            f"private_key_bytes must be exactly {_PRIVATE_KEY_LEN} bytes, "
            f"got {len(private_key_bytes)}"
        )
    return Ed25519PrivateKey.from_private_bytes(private_key_bytes)


def load_public_key(public_key_bytes: bytes) -> Ed25519PublicKey:
    """Parse a 32-byte raw Ed25519 public key."""
    if not isinstance(public_key_bytes, bytes):
        raise TypeError("public_key_bytes must be bytes")
    if len(public_key_bytes) != _PUBLIC_KEY_LEN:
        raise ValueError(
            f"public_key_bytes must be exactly {_PUBLIC_KEY_LEN} bytes, "
            f"got {len(public_key_bytes)}"
        )
    return Ed25519PublicKey.from_public_bytes(public_key_bytes)


def _serialise_private(key: Ed25519PrivateKey) -> bytes:
    return key.private_bytes(
        encoding=Encoding.Raw,
        format=PrivateFormat.Raw,
        encryption_algorithm=NoEncryption(),
    )


def _serialise_public(key: Ed25519PublicKey) -> bytes:
    return key.public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)

"""Tests for packages.crypto.encrypt (CP9.35 / NEW-P10.X.ma-export-encryption-at-rest)."""

from __future__ import annotations

import base64
import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from packages.crypto.encrypt import (
    SCHEME_V1,
    CipherEnvelope,
    DecryptError,
    EncryptError,
    decrypt_for_recipient,
    encrypt_for_recipient,
    generate_x25519_keypair,
)

# ---------- generate_x25519_keypair ----------


def test_generate_keypair_returns_32_byte_halves() -> None:
    priv, pub = generate_x25519_keypair()
    assert isinstance(priv, bytes)
    assert isinstance(pub, bytes)
    assert len(priv) == 32
    assert len(pub) == 32


def test_generate_keypair_is_random() -> None:
    """Two calls produce different keypairs (no deterministic clock seed)."""
    p1, u1 = generate_x25519_keypair()
    p2, u2 = generate_x25519_keypair()
    assert p1 != p2
    assert u1 != u2


# ---------- roundtrip happy path ----------


def test_encrypt_decrypt_roundtrip_hello_world() -> None:
    priv, pub = generate_x25519_keypair()
    plaintext = b"hello world"
    envelope = encrypt_for_recipient(plaintext, recipient_public_key=pub)
    recovered = decrypt_for_recipient(envelope, recipient_private_key=priv)
    assert recovered == plaintext


def test_encrypt_decrypt_roundtrip_empty_plaintext() -> None:
    priv, pub = generate_x25519_keypair()
    envelope = encrypt_for_recipient(b"", recipient_public_key=pub)
    recovered = decrypt_for_recipient(envelope, recipient_private_key=priv)
    assert recovered == b""


def test_encrypt_decrypt_roundtrip_large_plaintext() -> None:
    """1 MB of random-ish bytes roundtrips."""
    priv, pub = generate_x25519_keypair()
    plaintext = (b"\x00\x01\x02\x03" * 256_000)[:1_000_000]
    envelope = encrypt_for_recipient(plaintext, recipient_public_key=pub)
    recovered = decrypt_for_recipient(envelope, recipient_private_key=priv)
    assert recovered == plaintext


def test_encrypt_decrypt_json_payload_roundtrip() -> None:
    """The canonical use-case: encrypt a JSON-serialised MaDiligenceExport."""
    priv, pub = generate_x25519_keypair()
    payload = json.dumps({"hello": "world", "n": 42}).encode("utf-8")
    envelope = encrypt_for_recipient(payload, recipient_public_key=pub)
    recovered = decrypt_for_recipient(envelope, recipient_private_key=priv)
    assert json.loads(recovered) == {"hello": "world", "n": 42}


# ---------- envelope wire-form ----------


def test_envelope_scheme_is_versioned() -> None:
    _, pub = generate_x25519_keypair()
    envelope = encrypt_for_recipient(b"x", recipient_public_key=pub)
    assert envelope.scheme == "x25519-chacha20poly1305-v1"
    assert envelope.scheme == SCHEME_V1


def test_envelope_fields_are_base64_decodable() -> None:
    _, pub = generate_x25519_keypair()
    envelope = encrypt_for_recipient(b"x", recipient_public_key=pub)
    eph = base64.b64decode(envelope.ephemeral_public_key_b64)
    nonce = base64.b64decode(envelope.nonce_b64)
    ct = base64.b64decode(envelope.ciphertext_b64)
    assert len(eph) == 32
    assert len(nonce) == 12
    # Ciphertext for b"x" = 1 byte plaintext + 16 byte tag = 17 bytes minimum.
    assert len(ct) >= 16


def test_envelope_is_json_safe_via_model_dump() -> None:
    _, pub = generate_x25519_keypair()
    envelope = encrypt_for_recipient(b"payload", recipient_public_key=pub)
    dumped = envelope.model_dump(mode="json")
    # Must round-trip through json.dumps/json.loads without errors.
    s = json.dumps(dumped)
    parsed = json.loads(s)
    rebuilt = CipherEnvelope.model_validate(parsed)
    assert rebuilt == envelope


def test_envelope_is_frozen() -> None:
    _, pub = generate_x25519_keypair()
    envelope = encrypt_for_recipient(b"x", recipient_public_key=pub)
    with pytest.raises(ValidationError):
        envelope.scheme = "tampered"  # type: ignore[misc]


# ---------- encrypt input validation ----------


def test_encrypt_rejects_wrong_length_public_key() -> None:
    with pytest.raises(EncryptError, match="32 bytes"):
        encrypt_for_recipient(b"hello", recipient_public_key=b"\x00" * 16)


def test_encrypt_rejects_empty_public_key() -> None:
    with pytest.raises(EncryptError, match="32 bytes"):
        encrypt_for_recipient(b"hello", recipient_public_key=b"")


# ---------- ephemeral key randomness ----------


def test_encrypt_uses_fresh_ephemeral_key_each_call() -> None:
    """Same plaintext + same recipient key -> different envelope every time."""
    _, pub = generate_x25519_keypair()
    e1 = encrypt_for_recipient(b"same", recipient_public_key=pub)
    e2 = encrypt_for_recipient(b"same", recipient_public_key=pub)
    assert e1.ephemeral_public_key_b64 != e2.ephemeral_public_key_b64
    assert e1.ciphertext_b64 != e2.ciphertext_b64
    assert e1.nonce_b64 != e2.nonce_b64


# ---------- decrypt input validation ----------


def test_decrypt_rejects_unknown_scheme() -> None:
    _, pub = generate_x25519_keypair()
    priv, _ = generate_x25519_keypair()
    real = encrypt_for_recipient(b"x", recipient_public_key=pub)
    forged = real.model_copy(update={"scheme": "aes-gcm-v2"})
    with pytest.raises(DecryptError, match="unsupported cipher scheme"):
        decrypt_for_recipient(forged, recipient_private_key=priv)


def test_decrypt_rejects_wrong_length_private_key() -> None:
    _, pub = generate_x25519_keypair()
    envelope = encrypt_for_recipient(b"x", recipient_public_key=pub)
    with pytest.raises(DecryptError, match="32 bytes"):
        decrypt_for_recipient(envelope, recipient_private_key=b"\x00" * 16)


def test_decrypt_rejects_malformed_base64() -> None:
    priv, pub = generate_x25519_keypair()
    real = encrypt_for_recipient(b"x", recipient_public_key=pub)
    forged = real.model_copy(update={"nonce_b64": "!!!not-base64!!!"})
    with pytest.raises(DecryptError, match="base64"):
        decrypt_for_recipient(forged, recipient_private_key=priv)


def test_decrypt_rejects_wrong_ephemeral_pubkey_length() -> None:
    priv, pub = generate_x25519_keypair()
    real = encrypt_for_recipient(b"x", recipient_public_key=pub)
    short_pub = base64.b64encode(b"\x00" * 16).decode("ascii")
    forged = real.model_copy(update={"ephemeral_public_key_b64": short_pub})
    with pytest.raises(DecryptError, match="ephemeral_public_key must be 32 bytes"):
        decrypt_for_recipient(forged, recipient_private_key=priv)


def test_decrypt_rejects_wrong_nonce_length() -> None:
    priv, pub = generate_x25519_keypair()
    real = encrypt_for_recipient(b"x", recipient_public_key=pub)
    short_nonce = base64.b64encode(b"\x00" * 8).decode("ascii")
    forged = real.model_copy(update={"nonce_b64": short_nonce})
    with pytest.raises(DecryptError, match="nonce must be 12 bytes"):
        decrypt_for_recipient(forged, recipient_private_key=priv)


# ---------- tamper detection ----------


def test_decrypt_fails_on_tampered_ciphertext() -> None:
    priv, pub = generate_x25519_keypair()
    envelope = encrypt_for_recipient(b"hello", recipient_public_key=pub)
    # Flip one bit in the ciphertext.
    ct = bytearray(base64.b64decode(envelope.ciphertext_b64))
    ct[0] ^= 0x01
    forged = envelope.model_copy(
        update={"ciphertext_b64": base64.b64encode(bytes(ct)).decode("ascii")}
    )
    with pytest.raises(DecryptError, match="AEAD decryption failed"):
        decrypt_for_recipient(forged, recipient_private_key=priv)


def test_decrypt_fails_on_tampered_nonce() -> None:
    priv, pub = generate_x25519_keypair()
    envelope = encrypt_for_recipient(b"hello", recipient_public_key=pub)
    bad_nonce = base64.b64encode(b"\xff" * 12).decode("ascii")
    forged = envelope.model_copy(update={"nonce_b64": bad_nonce})
    with pytest.raises(DecryptError, match="AEAD decryption failed"):
        decrypt_for_recipient(forged, recipient_private_key=priv)


def test_decrypt_fails_under_wrong_recipient_key() -> None:
    """Encrypted for recipient A, B tries to decrypt -> DecryptError."""
    _, pub_a = generate_x25519_keypair()
    priv_b, _ = generate_x25519_keypair()  # different recipient's private half
    envelope = encrypt_for_recipient(b"secret", recipient_public_key=pub_a)
    with pytest.raises(DecryptError, match="AEAD decryption failed"):
        decrypt_for_recipient(envelope, recipient_private_key=priv_b)


def test_decrypt_fails_on_tampered_ephemeral_pubkey() -> None:
    """Replace the ephemeral pubkey with a different valid X25519 pubkey -> tamper."""
    priv, pub = generate_x25519_keypair()
    envelope = encrypt_for_recipient(b"secret", recipient_public_key=pub)
    # Use ANOTHER valid 32-byte pubkey -- well-formed but wrong.
    _, other_pub = generate_x25519_keypair()
    forged = envelope.model_copy(
        update={"ephemeral_public_key_b64": base64.b64encode(other_pub).decode("ascii")}
    )
    with pytest.raises(DecryptError, match="AEAD decryption failed"):
        decrypt_for_recipient(forged, recipient_private_key=priv)


# ---------- Hypothesis: roundtrip on arbitrary bytes ----------


@given(plaintext=st.binary(min_size=0, max_size=2048))
@settings(max_examples=50, deadline=None)
def test_encrypt_decrypt_roundtrip_property(plaintext: bytes) -> None:
    priv, pub = generate_x25519_keypair()
    envelope = encrypt_for_recipient(plaintext, recipient_public_key=pub)
    recovered = decrypt_for_recipient(envelope, recipient_private_key=priv)
    assert recovered == plaintext

"""Tests for packages/crypto/sign.py - 100% branch coverage.

Unit tests + hypothesis property tests covering:
- generate_keypair: returns 32+32 bytes, fresh each call
- sign / verify happy path
- verify rejects: wrong signature length, malformed public key, tampered payload, wrong key
- load_private_key / load_public_key: type errors, length errors
- canonical-binding: signature is over canonical_json(payload), so key-order doesn't change it
"""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from hypothesis import given
from hypothesis import strategies as st

from packages.crypto.sign import (
    generate_keypair,
    load_private_key,
    load_public_key,
    sign,
    verify,
)

# ---------- generate_keypair ----------


def test_generate_keypair_returns_two_32_byte_values():
    priv, pub = generate_keypair()
    assert isinstance(priv, bytes)
    assert isinstance(pub, bytes)
    assert len(priv) == 32
    assert len(pub) == 32


def test_generate_keypair_is_fresh_each_call():
    a_priv, a_pub = generate_keypair()
    b_priv, b_pub = generate_keypair()
    assert a_priv != b_priv
    assert a_pub != b_pub


# ---------- sign / verify happy path ----------


def test_sign_returns_64_byte_signature():
    priv, _pub = generate_keypair()
    sig = sign(priv, {"hello": "world"})
    assert isinstance(sig, bytes)
    assert len(sig) == 64


def test_verify_accepts_valid_signature():
    priv, pub = generate_keypair()
    payload = {"event": "ingest", "n": 7}
    sig = sign(priv, payload)
    assert verify(pub, payload, sig) is True


def test_verify_is_canonical_key_order_irrelevant():
    """Signing {'a':1,'b':2} and verifying against {'b':2,'a':1} succeeds."""
    priv, pub = generate_keypair()
    sig = sign(priv, {"a": 1, "b": 2})
    assert verify(pub, {"b": 2, "a": 1}, sig) is True


# ---------- verify negative paths ----------


def test_verify_rejects_tampered_payload():
    priv, pub = generate_keypair()
    sig = sign(priv, {"n": 1})
    assert verify(pub, {"n": 2}, sig) is False


def test_verify_rejects_wrong_key():
    priv_a, _pub_a = generate_keypair()
    _priv_b, pub_b = generate_keypair()
    sig = sign(priv_a, {"x": True})
    assert verify(pub_b, {"x": True}, sig) is False


def test_verify_rejects_wrong_signature_length():
    _priv, pub = generate_keypair()
    assert verify(pub, {"x": 1}, b"\x00" * 63) is False
    assert verify(pub, {"x": 1}, b"\x00" * 65) is False
    assert verify(pub, {"x": 1}, b"") is False


def test_verify_rejects_malformed_public_key():
    priv, _pub = generate_keypair()
    sig = sign(priv, {"x": 1})
    # 32 bytes of zeros is a valid-length public-key encoding but unrelated;
    # verification must fail without raising.
    assert verify(b"\x00" * 32, {"x": 1}, sig) is False


def test_verify_returns_false_on_short_public_key():
    """load_public_key raises ValueError; verify must swallow and return False."""
    priv, _pub = generate_keypair()
    sig = sign(priv, {"x": 1})
    assert verify(b"\x00" * 16, {"x": 1}, sig) is False


# ---------- load_private_key / load_public_key ----------


def test_load_private_key_returns_ed25519_private():
    priv, _pub = generate_keypair()
    assert isinstance(load_private_key(priv), Ed25519PrivateKey)


def test_load_public_key_returns_ed25519_public():
    _priv, pub = generate_keypair()
    assert isinstance(load_public_key(pub), Ed25519PublicKey)


def test_load_private_key_rejects_non_bytes():
    with pytest.raises(TypeError, match="must be bytes"):
        load_private_key("not bytes")  # type: ignore[arg-type]


def test_load_public_key_rejects_non_bytes():
    with pytest.raises(TypeError, match="must be bytes"):
        load_public_key(["not", "bytes"])  # type: ignore[arg-type]


def test_load_private_key_rejects_wrong_length():
    with pytest.raises(ValueError, match="must be exactly 32 bytes"):
        load_private_key(b"\x00" * 31)


def test_load_public_key_rejects_wrong_length():
    with pytest.raises(ValueError, match="must be exactly 32 bytes"):
        load_public_key(b"\x00" * 33)


# ---------- Hypothesis property tests ----------


_json_primitives = st.one_of(
    st.text(max_size=20),
    st.integers(min_value=-(2**31), max_value=2**31 - 1),
    st.booleans(),
)


@given(
    st.dictionaries(
        keys=st.text(min_size=1, max_size=10),
        values=_json_primitives,
        max_size=8,
    )
)
def test_sign_then_verify_property(payload):
    """For any canonicalisable payload, sign-then-verify round-trips True."""
    priv, pub = generate_keypair()
    sig = sign(priv, payload)
    assert verify(pub, payload, sig) is True


@given(st.binary(min_size=64, max_size=64))
def test_verify_rejects_random_signatures_property(sig):
    """Random 64-byte blobs almost never verify as a real signature."""
    _priv, pub = generate_keypair()
    # The probability of a random 64-byte blob being a valid Ed25519 signature
    # for any given (key, payload) is ~2^-256. Effectively zero.
    assert verify(pub, {"fixed": "payload"}, sig) is False

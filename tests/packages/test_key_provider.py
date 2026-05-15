"""Tests for packages.crypto.key_provider (CP9.41 / NEW-P10.X.kms-adapter)."""

from __future__ import annotations

import pytest

from packages.crypto.encrypt import (
    DecryptError,
    encrypt_for_recipient,
    generate_x25519_keypair,
)
from packages.crypto.key_provider import (
    AwsKmsX25519KeyProvider,
    InMemoryX25519KeyProvider,
    KeyProviderError,
    X25519PrivateKeyProvider,
    decrypt_via_provider,
)

# ---------- InMemoryX25519KeyProvider construction ----------


def test_in_memory_provider_constructs_from_32_byte_key() -> None:
    priv, _ = generate_x25519_keypair()
    provider = InMemoryX25519KeyProvider(priv)
    assert isinstance(provider, X25519PrivateKeyProvider)


def test_in_memory_provider_rejects_non_bytes_input() -> None:
    with pytest.raises(KeyProviderError, match="must be bytes"):
        InMemoryX25519KeyProvider("a string")  # type: ignore[arg-type]


def test_in_memory_provider_rejects_wrong_length() -> None:
    with pytest.raises(KeyProviderError, match="32 bytes"):
        InMemoryX25519KeyProvider(b"\x00" * 16)


def test_in_memory_provider_rejects_empty_bytes() -> None:
    with pytest.raises(KeyProviderError, match="32 bytes"):
        InMemoryX25519KeyProvider(b"")


# ---------- InMemoryX25519KeyProvider.decrypt ----------


@pytest.mark.asyncio
async def test_in_memory_provider_roundtrips_hello_world() -> None:
    priv, pub = generate_x25519_keypair()
    envelope = encrypt_for_recipient(b"hello", recipient_public_key=pub)
    provider = InMemoryX25519KeyProvider(priv)
    assert await provider.decrypt(envelope) == b"hello"


@pytest.mark.asyncio
async def test_in_memory_provider_roundtrips_empty_plaintext() -> None:
    priv, pub = generate_x25519_keypair()
    envelope = encrypt_for_recipient(b"", recipient_public_key=pub)
    provider = InMemoryX25519KeyProvider(priv)
    assert await provider.decrypt(envelope) == b""


@pytest.mark.asyncio
async def test_in_memory_provider_decrypt_raises_decrypt_error_on_wrong_key() -> None:
    """Cryptographic failure -> DecryptError, NOT KeyProviderError.

    The provider type discriminates: KeyProviderError means "couldn't get
    the key" (KMS down, key not found, wrong ARN); DecryptError means
    "got the key but the math failed" (wrong key, tampered ciphertext).
    Two different operational classes that need different runbooks.
    """
    priv_a, _ = generate_x25519_keypair()
    _, pub_b = generate_x25519_keypair()
    envelope = encrypt_for_recipient(b"secret", recipient_public_key=pub_b)
    provider = InMemoryX25519KeyProvider(priv_a)  # wrong key
    with pytest.raises(DecryptError):
        await provider.decrypt(envelope)


# ---------- decrypt_via_provider convenience wrapper ----------


@pytest.mark.asyncio
async def test_decrypt_via_provider_delegates_to_provider() -> None:
    priv, pub = generate_x25519_keypair()
    envelope = encrypt_for_recipient(b"via wrapper", recipient_public_key=pub)
    provider = InMemoryX25519KeyProvider(priv)
    result = await decrypt_via_provider(envelope, provider=provider)
    assert result == b"via wrapper"


# ---------- AwsKmsX25519KeyProvider construction (the stub) ----------


def test_aws_kms_provider_constructs_with_valid_inputs() -> None:
    provider = AwsKmsX25519KeyProvider(
        kms_key_arn="arn:aws:kms:us-east-1:123:key/abc",
        wrapped_private_key_ciphertext=b"\x01\x02\x03",
    )
    assert isinstance(provider, X25519PrivateKeyProvider)


def test_aws_kms_provider_rejects_empty_arn() -> None:
    with pytest.raises(KeyProviderError, match="kms_key_arn"):
        AwsKmsX25519KeyProvider(
            kms_key_arn="",
            wrapped_private_key_ciphertext=b"\x01",
        )


def test_aws_kms_provider_rejects_whitespace_arn() -> None:
    with pytest.raises(KeyProviderError, match="kms_key_arn"):
        AwsKmsX25519KeyProvider(
            kms_key_arn="   ",
            wrapped_private_key_ciphertext=b"\x01",
        )


def test_aws_kms_provider_rejects_empty_wrapped_ciphertext() -> None:
    with pytest.raises(KeyProviderError, match="wrapped_private_key_ciphertext"):
        AwsKmsX25519KeyProvider(
            kms_key_arn="arn:aws:kms:us-east-1:123:key/abc",
            wrapped_private_key_ciphertext=b"",
        )


def test_aws_kms_provider_accepts_custom_region() -> None:
    """region kwarg has a default; non-default values are accepted."""
    provider = AwsKmsX25519KeyProvider(
        kms_key_arn="arn:aws:kms:eu-west-2:123:key/abc",
        wrapped_private_key_ciphertext=b"\x01\x02",
        region="eu-west-2",
    )
    # No assertion on internals beyond construction succeeding -- the
    # stub explicitly captures region for the future impl.
    assert isinstance(provider, X25519PrivateKeyProvider)


# ---------- ABC contract enforcement ----------


def test_abc_cannot_be_instantiated_directly() -> None:
    """Direct instantiation of the ABC must fail."""
    with pytest.raises(TypeError):
        X25519PrivateKeyProvider()  # type: ignore[abstract]


def test_in_memory_provider_isinstance_of_abc() -> None:
    priv, _ = generate_x25519_keypair()
    provider = InMemoryX25519KeyProvider(priv)
    assert isinstance(provider, X25519PrivateKeyProvider)


def test_aws_kms_provider_isinstance_of_abc() -> None:
    provider = AwsKmsX25519KeyProvider(
        kms_key_arn="arn:aws:kms:us-east-1:123:key/abc",
        wrapped_private_key_ciphertext=b"\x01",
    )
    assert isinstance(provider, X25519PrivateKeyProvider)

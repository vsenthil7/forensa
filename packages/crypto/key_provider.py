"""packages.crypto.key_provider - decoupling key SOURCE from the encryption primitive.

CP9.41 / NEW-P10.X.kms-adapter. Same architectural pattern as
``TokenVerifier`` (apps.api.auth) and ``LobsterTrapClient`` /
``PolicyEnforcementClient`` (packages.policy.lobstertrap): a tiny ABC
defines the surface, today's bytes-in implementation is the in-process
default, and the production KMS-backed implementation is a clearly
named stub with its roadmap captured inline.

Why a separate module from packages.crypto.encrypt:

The encrypt module is a pure cryptographic primitive -- it takes 32 raw
bytes for the X25519 keypair and does the math. The KEY-SOURCING
question (process memory? AWS KMS? GCP Cloud KMS? HashiCorp Vault? HSM?)
is orthogonal. Mixing the two would force every encrypt-test to thread
through a provider mock. Keeping them separate means the encrypt module
stays trivially unit-testable AND callers who want production-grade key
custody can use the provider abstraction here.

Surface

    X25519PrivateKeyProvider(ABC)
        async def decrypt(envelope: CipherEnvelope) -> bytes

    InMemoryX25519KeyProvider(X25519PrivateKeyProvider)
        Constructed from 32 raw bytes. Used today by tests and by any
        deployment that hasn't wired a KMS yet.

    AwsKmsX25519KeyProvider(X25519PrivateKeyProvider)
        Stub. Raises ``NotImplementedError`` until the AWS KMS XChaCha
        adapter ships. Roadmap captured in its docstring.

    decrypt_via_provider(envelope, *, provider) -> bytes
        Convenience wrapper; the M&A export decryption path and any
        future caller use this. One call site change to swap key custody.

Production note: AWS KMS does NOT today expose X25519 raw decrypt
directly (it gives RSA / ECC P-256/384/521 / SM2). The production shape
is therefore "KMS-wrapped ephemeral X25519 keypair": at startup we
generate an X25519 keypair, encrypt the private key under a KMS CMK,
store the ciphertext, and decrypt on demand. The ``AwsKmsX25519KeyProvider``
stub captures that flow in its docstring. Same pattern as how AWS docs
describe key wrapping for envelope encryption.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from packages.crypto.encrypt import CipherEnvelope, decrypt_for_recipient

__all__ = [
    "AwsKmsX25519KeyProvider",
    "InMemoryX25519KeyProvider",
    "KeyProviderError",
    "X25519PrivateKeyProvider",
    "decrypt_via_provider",
]


class KeyProviderError(ValueError):
    """Raised when a key provider cannot fulfil a decrypt request.

    Distinct from ``DecryptError`` so callers can tell the difference
    between "the AEAD verification failed on a real key" and "the key
    source (KMS, Vault, HSM) was unavailable / misconfigured".
    """


class X25519PrivateKeyProvider(ABC):
    """Source of an X25519 private key for decrypting CipherEnvelopes.

    Implementations may hold the key in process memory (insecure but
    trivially testable), fetch it from a KMS / HSM at call time, or
    perform some hybrid (KMS-wrapped ephemeral keypair). Callers depend
    only on the ABC so the key-custody story can change without touching
    any call site beyond the wiring point.

    Why async: production providers (AWS KMS, GCP KMS, Vault) make HTTP
    calls. The in-memory provider is synchronous internally but exposes
    an async surface so all implementations are interchangeable.
    """

    @abstractmethod
    async def decrypt(self, envelope: CipherEnvelope) -> bytes:
        """Decrypt ``envelope`` and return the plaintext bytes.

        Implementations must raise ``DecryptError`` for cryptographic
        failures (wrong key, tampered ciphertext) and ``KeyProviderError``
        for sourcing failures (KMS unreachable, key not found, etc.).
        """


class InMemoryX25519KeyProvider(X25519PrivateKeyProvider):
    """Today's default: the X25519 private key lives in process memory.

    Use for tests and for deployments that haven't wired a KMS yet. NOT
    suitable for production-grade enterprise deployments handling real
    M&A bundles -- the bytes are observable via process inspection,
    crash dumps, and many other side channels.

    The constructor validates that the key is 32 bytes; any other length
    raises ``KeyProviderError`` before any decrypt call.
    """

    def __init__(self, private_key_bytes: bytes) -> None:
        if not isinstance(private_key_bytes, bytes):
            raise KeyProviderError(
                f"private_key_bytes must be bytes, got {type(private_key_bytes).__name__}"
            )
        if len(private_key_bytes) != 32:
            raise KeyProviderError(
                f"private_key_bytes must be 32 bytes X25519; got {len(private_key_bytes)}"
            )
        # Store directly. NOT a defensive copy -- bytes is immutable so
        # there's nothing to defend against. A future memzero hook could
        # land here.
        self._private_key_bytes = private_key_bytes

    async def decrypt(self, envelope: CipherEnvelope) -> bytes:
        # Delegate to the pure primitive. DecryptError bubbles up.
        return decrypt_for_recipient(envelope, recipient_private_key=self._private_key_bytes)


class AwsKmsX25519KeyProvider(X25519PrivateKeyProvider):
    """STUB: AWS KMS-backed X25519 key custody.

    This is a clearly-named stub that captures the production roadmap.
    Calling ``.decrypt()`` raises ``NotImplementedError`` until the real
    integration lands. The class exists today so:

    1. The X25519PrivateKeyProvider ABC has more than one named subclass
       (proves the ABC is genuine, not over-engineering for a single
       use case).
    2. The route layer can already type-hint
       ``provider: X25519PrivateKeyProvider`` without anyone having to
       guess what production will look like.
    3. The roadmap (envelope-encryption with a wrapped ephemeral
       keypair) is captured in code, not in scattered tickets.

    Production roadmap (NEW-P10.X.aws-kms-x25519-real-integration):

    AWS KMS does not expose X25519 raw decrypt directly. The standard
    pattern is "KMS envelope-encryption of an ephemeral X25519 keypair":

      Setup (one-time per tenant or per rotation period):
        1. Generate an X25519 keypair locally
        2. KMS.Encrypt(CMK=<tenant_cmk>, plaintext=<x25519_priv>) ->
           ``wrapped_priv``
        3. Persist (tenant_id, key_id, wrapped_priv, x25519_pub)
        4. Publish x25519_pub to acquirers (out-of-band, TLS-pinned)

      Decrypt (per envelope):
        1. Look up wrapped_priv by key_id from envelope.platform_key_id
        2. KMS.Decrypt(CMK=<tenant_cmk>, ciphertext=wrapped_priv) ->
           x25519_priv (in memory for the duration of this call only)
        3. Delegate to decrypt_for_recipient with that key
        4. Zeroise the temporary in-memory copy
        5. Return plaintext

    This shape gives KMS-grade key custody (CMK never leaves the HSM
    boundary) while keeping the wire format X25519+ChaCha20-Poly1305.

    Until then this stub keeps ``provider: X25519PrivateKeyProvider``
    type-safe at every call site.
    """

    def __init__(
        self,
        *,
        kms_key_arn: str,
        wrapped_private_key_ciphertext: bytes,
        region: str = "us-east-1",
    ) -> None:
        if not kms_key_arn or not kms_key_arn.strip():
            raise KeyProviderError("kms_key_arn must be non-empty")
        if not wrapped_private_key_ciphertext:
            raise KeyProviderError("wrapped_private_key_ciphertext must be non-empty")
        self._kms_key_arn = kms_key_arn
        self._wrapped = wrapped_private_key_ciphertext
        self._region = region

    async def decrypt(self, envelope: CipherEnvelope) -> bytes:  # pragma: no cover
        # No cover: this is the stub itself. The roadmap to a real impl
        # is captured in the class docstring; ship that impl in the
        # follow-up CP, NEW-P10.X.aws-kms-x25519-real-integration.
        raise NotImplementedError(
            "AwsKmsX25519KeyProvider is a roadmap stub; see the class docstring. "
            "Track NEW-P10.X.aws-kms-x25519-real-integration for the real impl."
        )


async def decrypt_via_provider(
    envelope: CipherEnvelope, *, provider: X25519PrivateKeyProvider
) -> bytes:
    """Convenience wrapper: ``await provider.decrypt(envelope)``.

    The route layer + integration tests use this so they don't have to
    pick which provider type to import. Same shape as
    ``decrypt_for_recipient`` but takes a provider instead of raw bytes.
    """
    return await provider.decrypt(envelope)

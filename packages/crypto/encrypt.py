"""packages.crypto.encrypt - hybrid X25519 + ChaCha20-Poly1305 encryption.

The "encrypt a JSON blob for a known recipient" primitive used by export
modules. Same shape as NaCl's `crypto_box` and libsodium's
`sealed_box`: ephemeral X25519 key exchange + ChaCha20-Poly1305 AEAD
under the shared secret.

CP9.35 / NEW-P10.X.ma-export-encryption-at-rest. First caller is the M&A
export route which encrypts the sealed bundle with the acquirer's
published public key so only they can decrypt it.

Why X25519 + ChaCha20-Poly1305 (not RSA-OAEP + AES-GCM):

- X25519 is fast, constant-time, has small (32-byte) keys.
- ChaCha20-Poly1305 is constant-time on every CPU (AES-GCM only on AES-NI
  hardware); important for our mostly-Python deployment surface.
- 24-byte nonces from RFC 8439 XChaCha20 are large enough to be random
  rather than counter-managed. We use the 12-byte ChaCha20-Poly1305
  nonce here; the ephemeral key per encryption makes nonce reuse impossible
  in practice.
- Same primitives Sigstore Cosign uses for keyless signing (well-audited
  ecosystem).

Wire format (CipherEnvelope):

  {
    "scheme": "x25519-chacha20poly1305-v1",
    "ephemeral_public_key_b64": <32 bytes base64>,
    "nonce_b64": <12 bytes base64>,
    "ciphertext_b64": <variable; ciphertext + 16-byte Poly1305 tag>
  }

Decryption (recipient holds their X25519 private key):

  1. X25519 ECDH between recipient_priv and ephemeral_pub -> shared 32 bytes
  2. HKDF-SHA256 over shared secret -> 32-byte ChaCha20-Poly1305 key
  3. ChaCha20-Poly1305.decrypt(key, nonce, ciphertext) -> plaintext

The decrypt function returns the plaintext bytes; the caller parses as
JSON. Tamper detection is automatic: Poly1305 tag is verified before
the decrypt returns.

PRODUCTION NOTES:

- Production keys live in the recipient's KMS / HSM, not bytes in Python.
  This module's bytes-in API is the interop primitive; an
  X25519PrivateKeyProvider ABC (analogous to TokenVerifier) would be the
  production wrap. Tracked as NEW-P10.X.kms-adapter.
- The recipient's public key must be distributed out-of-band (TLS-pinned
  download, contractual exchange, on-paper at deal close). This module
  doesn't address key distribution.
- 100% line + branch coverage via the unit tests in
  tests/packages/test_encrypt.py. Hypothesis property test for roundtrip
  on arbitrary plaintext bytes.
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "CipherEnvelope",
    "DecryptError",
    "EncryptError",
    "decrypt_for_recipient",
    "encrypt_for_recipient",
    "generate_x25519_keypair",
]

SCHEME_V1 = "x25519-chacha20poly1305-v1"
_NONCE_BYTES = 12
_KEY_BYTES = 32
_HKDF_INFO = b"forensa:export:cipher:v1"


class EncryptError(ValueError):
    """Raised when encryption cannot be performed (e.g. bad public key)."""


class DecryptError(ValueError):
    """Raised when decryption fails (bad key, tampered ciphertext, etc.).

    Returned as a single exception type so callers cannot distinguish
    "wrong key" from "tampered ciphertext" via response timing or
    exception class -- same security posture as bcrypt/argon2 returning
    a generic "verification failed".
    """


class CipherEnvelope(BaseModel):
    """Wire form for an encrypted payload.

    All bytes fields are base64-encoded for JSON transport (raw bytes
    can't ride in JSON). Pydantic v2 frozen + extra=forbid for the strict
    inbound contract the M&A export route requires.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    scheme: str = Field(
        ...,
        description="Cipher scheme identifier; currently always 'x25519-chacha20poly1305-v1'",
    )
    ephemeral_public_key_b64: str = Field(
        ..., description="Ephemeral X25519 public key, base64-encoded (32 bytes)"
    )
    nonce_b64: str = Field(..., description="ChaCha20-Poly1305 nonce, base64-encoded (12 bytes)")
    ciphertext_b64: str = Field(
        ..., description="ChaCha20-Poly1305 ciphertext + 16-byte Poly1305 tag, base64-encoded"
    )


def generate_x25519_keypair() -> tuple[bytes, bytes]:
    """Generate a fresh X25519 keypair.

    Returns
    -------
    tuple[bytes, bytes]
        (private_key_bytes, public_key_bytes), each 32 bytes raw.

    Suitable for tests and as the seed of the M&A acquirer's published
    keypair (real production keys live in the acquirer's KMS / HSM and
    only the public half is shared with Forensa).
    """
    priv = x25519.X25519PrivateKey.generate()
    priv_bytes = priv.private_bytes_raw()
    pub_bytes = priv.public_key().public_bytes_raw()
    return priv_bytes, pub_bytes


def _derive_aead_key(shared_secret: bytes) -> bytes:
    """HKDF-SHA256 to a 32-byte ChaCha20-Poly1305 key."""
    return HKDF(
        algorithm=hashes.SHA256(),
        length=_KEY_BYTES,
        salt=None,
        info=_HKDF_INFO,
    ).derive(shared_secret)


def encrypt_for_recipient(
    plaintext: bytes,
    *,
    recipient_public_key: bytes,
) -> CipherEnvelope:
    """Encrypt ``plaintext`` for the holder of ``recipient_public_key``.

    Generates an ephemeral X25519 keypair, performs ECDH with the
    recipient's public key, HKDFs the shared secret to a 32-byte
    ChaCha20-Poly1305 key, then AEAD-encrypts plaintext under that key
    with a fresh random nonce.

    Parameters
    ----------
    plaintext : bytes
        Arbitrary plaintext to encrypt. Typically the canonical JSON of a
        MaDiligenceExport.
    recipient_public_key : bytes
        32 bytes X25519 public key.

    Returns
    -------
    CipherEnvelope
        The encrypted payload + ephemeral pubkey + nonce. Wire-form via
        ``model_dump(mode='json')`` is JSON-safe.

    Raises
    ------
    EncryptError
        If ``recipient_public_key`` is not 32 bytes or any cryptographic
        primitive raises.
    """
    if len(recipient_public_key) != _KEY_BYTES:
        raise EncryptError(
            f"recipient_public_key must be 32 bytes X25519; got {len(recipient_public_key)}"
        )
    try:
        recipient_pub = x25519.X25519PublicKey.from_public_bytes(recipient_public_key)
    except (ValueError, Exception) as exc:
        raise EncryptError(f"recipient_public_key is not a valid X25519 point: {exc}") from exc

    # Ephemeral keypair: fresh per call, throws after.
    ephemeral_priv = x25519.X25519PrivateKey.generate()
    ephemeral_pub_bytes = ephemeral_priv.public_key().public_bytes_raw()

    # ECDH -> shared secret -> AEAD key.
    shared = ephemeral_priv.exchange(recipient_pub)
    aead_key = _derive_aead_key(shared)

    # Encrypt with random nonce; AEAD provides authenticity tag.
    nonce = os.urandom(_NONCE_BYTES)
    aead = ChaCha20Poly1305(aead_key)
    ciphertext = aead.encrypt(nonce, plaintext, associated_data=None)

    return CipherEnvelope(
        scheme=SCHEME_V1,
        ephemeral_public_key_b64=base64.b64encode(ephemeral_pub_bytes).decode("ascii"),
        nonce_b64=base64.b64encode(nonce).decode("ascii"),
        ciphertext_b64=base64.b64encode(ciphertext).decode("ascii"),
    )


def decrypt_for_recipient(
    envelope: CipherEnvelope,
    *,
    recipient_private_key: bytes,
) -> bytes:
    """Decrypt a ``CipherEnvelope`` produced by ``encrypt_for_recipient``.

    Parameters
    ----------
    envelope : CipherEnvelope
        The encrypted payload.
    recipient_private_key : bytes
        32 bytes X25519 private key paired with the public key used to
        encrypt.

    Returns
    -------
    bytes
        The original plaintext bytes.

    Raises
    ------
    DecryptError
        On any failure: wrong scheme, malformed key, malformed envelope
        fields, AEAD tag verification failure (tampered ciphertext OR
        wrong key). Generic exception class -- callers cannot distinguish
        attacker-detectable failure modes from each other.
    """
    if envelope.scheme != SCHEME_V1:
        raise DecryptError(f"unsupported cipher scheme: {envelope.scheme!r}")
    if len(recipient_private_key) != _KEY_BYTES:
        raise DecryptError(
            f"recipient_private_key must be 32 bytes X25519; got {len(recipient_private_key)}"
        )
    try:
        recipient_priv = x25519.X25519PrivateKey.from_private_bytes(recipient_private_key)
    except (ValueError, Exception) as exc:
        raise DecryptError(f"recipient_private_key is not a valid X25519 key: {exc}") from exc

    try:
        ephemeral_pub_bytes = base64.b64decode(envelope.ephemeral_public_key_b64)
        nonce = base64.b64decode(envelope.nonce_b64)
        ciphertext = base64.b64decode(envelope.ciphertext_b64)
    except (ValueError, Exception) as exc:
        raise DecryptError(f"envelope base64 decode failed: {exc}") from exc

    if len(ephemeral_pub_bytes) != _KEY_BYTES:
        raise DecryptError("ephemeral_public_key must be 32 bytes")
    if len(nonce) != _NONCE_BYTES:
        raise DecryptError("nonce must be 12 bytes")

    try:
        ephemeral_pub = x25519.X25519PublicKey.from_public_bytes(ephemeral_pub_bytes)
    except (ValueError, Exception) as exc:
        raise DecryptError(f"ephemeral_public_key invalid: {exc}") from exc

    # ECDH -> shared secret -> AEAD key.
    shared = recipient_priv.exchange(ephemeral_pub)
    aead_key = _derive_aead_key(shared)

    # Decrypt. ChaCha20-Poly1305 raises InvalidTag on tamper / wrong key;
    # we wrap as DecryptError so callers see one exception type.
    aead = ChaCha20Poly1305(aead_key)
    try:
        plaintext = aead.decrypt(nonce, ciphertext, associated_data=None)
    except Exception as exc:
        raise DecryptError(f"AEAD decryption failed (tampered or wrong key): {exc}") from exc

    return plaintext

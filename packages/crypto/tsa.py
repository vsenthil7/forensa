"""packages.crypto.tsa - RFC 3161 timestamp authority client (CP9.19 / BR-06).

The receipt ledger today binds ``signed_at`` to ``datetime.now(UTC)`` - a
server clock value. A regulator with T+1 year doubt cannot prove the
server clock wasn't set wrong. BR-06 says the chain must be anchored by
an external trusted timestamp authority on a daily cadence.

This module defines the abstraction. ``TimestampClient`` is an ABC; two
concrete impls are provided:

- ``MockTimestampClient``: deterministic, in-process, no network. Signs
  the requested hash with a fixed local Ed25519 keypair representing the
  "TSA". Used by tests and the hackathon demo. Production swaps this for
  ``Rfc3161TimestampClient``.

- ``Rfc3161TimestampClient``: skeleton interface for a real TSA over HTTP
  per RFC 3161 §3.4. Marked PRODUCTION-DEFERRED in CP9.19; the test seam
  is in place but the full ASN.1 DER encoding + HTTP POST + cert-chain
  verification is CP10.x scope.

The wire form of a ``TimestampResponse`` is a frozen Pydantic model:

- ``tsa_identifier``: opaque str identifying which TSA produced this
  response (e.g. "freetsa.org" or "forensa-mock-2026").
- ``tsr_bytes``: the raw TSR bytes (real impl: ASN.1 DER; mock: a
  deterministic JSON encoding).
- ``timestamped_at``: when the TSA claims the hash was timestamped.
- ``hashed_root``: the hex SHA-256 the caller asked to be timestamped.
- ``signature``: the TSA's signature over (hashed_root + timestamped_at).

A regulator with the TSA's public key can verify ``signature`` against
``(hashed_root, timestamped_at)`` and prove the receipt root existed at
``timestamped_at``. Forensa persists ``TimestampResponse`` as a
``TimestampAnchorRow`` in the DB (CP9.19 alembic 0007).

Security note
-------------

The mock TSA is NOT a real trust anchor. It's a deterministic stand-in
for the protocol shape. Production deployments MUST configure
``Rfc3161TimestampClient`` against a real TSA (FreeTSA, DigiCert,
Sectigo, etc.) before claiming RFC 3161 compliance.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from packages.crypto.sign import generate_keypair
from packages.crypto.sign import sign as ed25519_sign

__all__ = [
    "MockTimestampClient",
    "Rfc3161TimestampClient",
    "TimestampClient",
    "TimestampClientError",
    "TimestampResponse",
    "verify_timestamp_response",
]


class TimestampClientError(Exception):
    """Raised when the TSA client fails to produce a valid timestamp.

    Wraps any underlying transport or protocol error so callers map a
    single exception type to "TSA unavailable; anchoring deferred".
    """


class TimestampResponse(BaseModel):
    """The TSA's signed acknowledgement of a hash + timestamp pairing.

    All fields are required and immutable. Equality is structural so two
    instances with identical fields compare equal (useful for replay
    verification).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    tsa_identifier: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Opaque TSA identifier, e.g. 'freetsa.org' or 'forensa-mock-2026'",
    )
    tsr_bytes: bytes = Field(
        ...,
        description=(
            "Raw TSR bytes. Production: ASN.1 DER per RFC 3161. Mock: deterministic JSON."
        ),
    )
    timestamped_at: datetime = Field(
        ...,
        description="When the TSA claims this hash was witnessed (tz-aware).",
    )
    hashed_root: str = Field(
        ...,
        min_length=64,
        max_length=64,
        pattern="^[0-9a-f]{64}$",
        description="The lowercase-hex SHA-256 the caller asked to be timestamped.",
    )
    signature: bytes = Field(
        ...,
        description="TSA's Ed25519 signature over canonical (hashed_root, timestamped_at).",
    )


def _canonical_sign_payload(hashed_root: str, timestamped_at: datetime) -> bytes:
    """Build the byte string the TSA signs.

    Deterministic JSON encoding of ``{hashed_root, timestamped_at}`` so
    verifiers in any language can reproduce the bytes and check the sig.
    """
    return json.dumps(
        {"hashed_root": hashed_root, "timestamped_at": timestamped_at.isoformat()},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


class TimestampClient(ABC):
    """Submit a hash to a TSA; receive a signed ``TimestampResponse``.

    The contract is intentionally narrow:

    - ``request_timestamp(hashed_root)`` -> ``TimestampResponse``.
    - Implementations must raise ``TimestampClientError`` on any failure
      so the caller can persist a "TSA unavailable; retry tomorrow" tombstone
      instead of corrupting the anchor ledger with a half-signed row.

    Implementations are NOT required to be idempotent: re-calling for the
    same hash MAY return a new TSR with a later timestamp. Callers wishing
    idempotency cache the response themselves.
    """

    @abstractmethod
    async def request_timestamp(self, hashed_root: str) -> TimestampResponse:
        """Submit ``hashed_root`` (64 lowercase hex chars) to the TSA."""


class MockTimestampClient(TimestampClient):
    """In-process deterministic TSA. Signs with a local Ed25519 keypair.

    The public key is exposed via :attr:`public_key` so tests can verify
    the response signature without monkeypatching. The mock's identifier
    defaults to ``"forensa-mock-2026"`` but can be overridden.

    The mock is constructed with an optional ``fixed_clock`` callable for
    deterministic time-stamping in tests; production code uses
    ``datetime.now(UTC)`` via the default.
    """

    def __init__(
        self,
        *,
        identifier: str = "forensa-mock-2026",
        clock: type[datetime] | None = None,
    ) -> None:
        self._identifier = identifier
        self._clock = clock or datetime
        priv, pub = generate_keypair()
        self._private_key = priv
        self._public_key = pub

    @property
    def public_key(self) -> bytes:
        """The mock TSA's public key (32 bytes Ed25519). Used by verifiers."""
        return self._public_key

    @property
    def identifier(self) -> str:
        return self._identifier

    async def request_timestamp(self, hashed_root: str) -> TimestampResponse:
        if not (len(hashed_root) == 64 and all(c in "0123456789abcdef" for c in hashed_root)):
            raise TimestampClientError(
                f"hashed_root must be 64 lowercase hex chars; got {hashed_root!r}"
            )
        now = self._clock.now(UTC)
        payload_bytes = _canonical_sign_payload(hashed_root, now)
        signature = ed25519_sign(self._private_key, payload_bytes)
        # Mock TSR bytes: a deterministic JSON envelope. Production replaces
        # with ASN.1 DER per RFC 3161 §3.5.
        tsr_bytes = json.dumps(
            {
                "tsa": self._identifier,
                "hashed_root": hashed_root,
                "timestamped_at": now.isoformat(),
                "signature_hex": signature.hex(),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return TimestampResponse(
            tsa_identifier=self._identifier,
            tsr_bytes=tsr_bytes,
            timestamped_at=now,
            hashed_root=hashed_root,
            signature=signature,
        )


class Rfc3161TimestampClient(TimestampClient):
    """Real RFC 3161 TSA over HTTP. PRODUCTION-DEFERRED.

    Constructor accepts a TSA endpoint URL and a CA-bundle path for cert
    verification. The actual ``request_timestamp`` implementation is
    deferred to CP10.x because real RFC 3161 requires:

    - ASN.1 DER encoding of the TimeStampReq (rfc3161ng or asn1crypto).
    - HTTP POST with ``Content-Type: application/timestamp-query``.
    - Parsing the TimeStampResp.
    - Verifying the TSA cert against a trust anchor.
    - Extracting the genTime field.

    Today it raises ``TimestampClientError`` immediately so any
    accidental production wire-up fails LOUDLY rather than silently
    falling back to a server-clock value.
    """

    def __init__(self, *, endpoint_url: str, ca_bundle_path: str | None = None) -> None:
        if not endpoint_url.startswith(("http://", "https://")):
            raise ValueError(f"endpoint_url must be http(s) URL; got {endpoint_url!r}")
        self._endpoint_url = endpoint_url
        self._ca_bundle_path = ca_bundle_path

    @property
    def endpoint_url(self) -> str:
        return self._endpoint_url

    async def request_timestamp(self, hashed_root: str) -> TimestampResponse:
        raise TimestampClientError(
            "Rfc3161TimestampClient is PRODUCTION-DEFERRED (CP10.x); "
            "configure MockTimestampClient for hackathon / dev / test."
        )


def verify_timestamp_response(
    response: TimestampResponse,
    *,
    tsa_public_key: bytes,
) -> bool:
    """Verify ``response.signature`` against ``response.hashed_root`` + ``timestamped_at``.

    Returns True iff the TSA's signature is valid under ``tsa_public_key``.
    Used by regulators to prove that the anchored root existed at the
    claimed timestamp. Non-raising: returns False on any verification
    failure including malformed inputs.
    """
    if len(tsa_public_key) != 32:
        return False
    payload_bytes = _canonical_sign_payload(response.hashed_root, response.timestamped_at)
    # Use hmac.compare_digest indirectly via the underlying ed25519 verify
    # function from packages.crypto.sign. The non-raising semantics there
    # match what we want here.
    from packages.crypto.sign import verify as ed25519_verify

    return ed25519_verify(tsa_public_key, payload_bytes, response.signature)

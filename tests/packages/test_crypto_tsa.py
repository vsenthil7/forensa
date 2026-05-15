"""Tests for packages.crypto.tsa (CP9.19 / BR-06)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from packages.crypto.sign import generate_keypair
from packages.crypto.tsa import (
    MockTimestampClient,
    Rfc3161TimestampClient,
    TimestampClient,
    TimestampClientError,
    TimestampResponse,
    verify_timestamp_response,
)

_VALID_HASH = "a" * 64


# ---------------------------------------------------------------------------
# TimestampResponse Pydantic model
# ---------------------------------------------------------------------------


def test_timestamp_response_is_frozen():
    """frozen=True - attempting to mutate any field raises."""
    response = _make_response()
    with pytest.raises((ValidationError, AttributeError, TypeError)):
        response.tsa_identifier = "evil"  # type: ignore[misc]


def test_timestamp_response_rejects_short_hashed_root():
    with pytest.raises(ValidationError):
        TimestampResponse(
            tsa_identifier="x",
            tsr_bytes=b"x",
            timestamped_at=datetime.now(UTC),
            hashed_root="too-short",
            signature=b"x" * 64,
        )


def test_timestamp_response_rejects_uppercase_hashed_root():
    """Pattern is lowercase hex - uppercase A-F rejected."""
    with pytest.raises(ValidationError):
        TimestampResponse(
            tsa_identifier="x",
            tsr_bytes=b"x",
            timestamped_at=datetime.now(UTC),
            hashed_root="A" * 64,
            signature=b"x" * 64,
        )


def test_timestamp_response_rejects_empty_tsa_identifier():
    with pytest.raises(ValidationError):
        TimestampResponse(
            tsa_identifier="",
            tsr_bytes=b"x",
            timestamped_at=datetime.now(UTC),
            hashed_root=_VALID_HASH,
            signature=b"x" * 64,
        )


def test_timestamp_response_extra_field_forbidden():
    with pytest.raises(ValidationError):
        TimestampResponse(
            tsa_identifier="x",
            tsr_bytes=b"x",
            timestamped_at=datetime.now(UTC),
            hashed_root=_VALID_HASH,
            signature=b"x" * 64,
            extra="boom",  # type: ignore[call-arg]
        )


def _make_response() -> TimestampResponse:
    return TimestampResponse(
        tsa_identifier="forensa-mock-2026",
        tsr_bytes=b"\x00" * 16,
        timestamped_at=datetime.now(UTC),
        hashed_root=_VALID_HASH,
        signature=b"\x00" * 64,
    )


# ---------------------------------------------------------------------------
# MockTimestampClient
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mock_client_returns_valid_response_for_good_hash():
    client = MockTimestampClient()
    response = await client.request_timestamp(_VALID_HASH)
    assert response.tsa_identifier == "forensa-mock-2026"
    assert response.hashed_root == _VALID_HASH
    assert response.timestamped_at.tzinfo == UTC
    assert len(response.signature) == 64
    assert response.tsr_bytes  # non-empty


@pytest.mark.asyncio
async def test_mock_client_signature_verifies_with_its_public_key():
    """The signature on the response MUST verify under client.public_key.
    This is the heart of the RFC 3161 anchor's regulator-verifiability."""
    client = MockTimestampClient()
    response = await client.request_timestamp(_VALID_HASH)
    assert verify_timestamp_response(response, tsa_public_key=client.public_key)


@pytest.mark.asyncio
async def test_mock_client_signature_does_not_verify_with_wrong_key():
    """Cross-key verification fails - critical security property."""
    client = MockTimestampClient()
    response = await client.request_timestamp(_VALID_HASH)
    _, wrong_pub = generate_keypair()
    assert not verify_timestamp_response(response, tsa_public_key=wrong_pub)


@pytest.mark.asyncio
async def test_mock_client_signature_does_not_verify_for_tampered_hash():
    """Modifying the response's hashed_root invalidates the signature.

    Mutating the immutable frozen Pydantic model isn't possible directly,
    so we forge a tampered copy and verify it fails.
    """
    client = MockTimestampClient()
    response = await client.request_timestamp(_VALID_HASH)
    tampered = TimestampResponse(
        tsa_identifier=response.tsa_identifier,
        tsr_bytes=response.tsr_bytes,
        timestamped_at=response.timestamped_at,
        hashed_root="b" * 64,  # different
        signature=response.signature,
    )
    assert not verify_timestamp_response(tampered, tsa_public_key=client.public_key)


@pytest.mark.asyncio
async def test_mock_client_rejects_short_hash():
    client = MockTimestampClient()
    with pytest.raises(TimestampClientError, match="64 lowercase hex"):
        await client.request_timestamp("too-short")


@pytest.mark.asyncio
async def test_mock_client_rejects_uppercase_hash():
    client = MockTimestampClient()
    with pytest.raises(TimestampClientError, match="64 lowercase hex"):
        await client.request_timestamp("A" * 64)


@pytest.mark.asyncio
async def test_mock_client_custom_identifier():
    client = MockTimestampClient(identifier="test-tsa-42")
    response = await client.request_timestamp(_VALID_HASH)
    assert response.tsa_identifier == "test-tsa-42"
    assert client.identifier == "test-tsa-42"


@pytest.mark.asyncio
async def test_mock_client_tsr_bytes_is_deterministic_json():
    """The mock's tsr_bytes is a JSON envelope a regulator's tool can
    inspect without a special parser. Verify it parses back correctly."""
    client = MockTimestampClient(identifier="test-tsa-43")
    response = await client.request_timestamp(_VALID_HASH)
    envelope = json.loads(response.tsr_bytes.decode("utf-8"))
    assert envelope["tsa"] == "test-tsa-43"
    assert envelope["hashed_root"] == _VALID_HASH
    assert envelope["signature_hex"] == response.signature.hex()


@pytest.mark.asyncio
async def test_mock_client_two_calls_produce_different_timestamps():
    """Each call has its own timestamp - the TSA is allowed to issue
    multiple timestamps for the same hash over time."""
    import asyncio

    client = MockTimestampClient()
    r1 = await client.request_timestamp(_VALID_HASH)
    await asyncio.sleep(0.001)  # ensure clock advances
    r2 = await client.request_timestamp(_VALID_HASH)
    assert r1.timestamped_at != r2.timestamped_at
    assert r1.signature != r2.signature  # different timestamp -> different sig


# ---------------------------------------------------------------------------
# Rfc3161TimestampClient - skeleton; PRODUCTION-DEFERRED
# ---------------------------------------------------------------------------


def test_rfc3161_client_constructor_validates_url_scheme():
    with pytest.raises(ValueError, match="http\\(s\\) URL"):
        Rfc3161TimestampClient(endpoint_url="ftp://tsa.example.com/")


def test_rfc3161_client_accepts_https_url():
    c = Rfc3161TimestampClient(endpoint_url="https://tsa.example.com/")
    assert c.endpoint_url == "https://tsa.example.com/"


def test_rfc3161_client_accepts_http_url():
    """Dev / test environments may use HTTP."""
    c = Rfc3161TimestampClient(endpoint_url="http://localhost:8080/tsa")
    assert c.endpoint_url == "http://localhost:8080/tsa"


def test_rfc3161_client_accepts_ca_bundle_path():
    c = Rfc3161TimestampClient(
        endpoint_url="https://tsa.example.com/",
        ca_bundle_path="/etc/ssl/certs/ca.pem",
    )
    assert c.endpoint_url == "https://tsa.example.com/"


@pytest.mark.asyncio
async def test_rfc3161_client_request_raises_production_deferred_error():
    """CP9.19 design: any production wire-up to Rfc3161 should FAIL LOUDLY
    until CP10.x lands. Silent fallback to server-clock is the failure
    mode we are explicitly preventing."""
    c = Rfc3161TimestampClient(endpoint_url="https://tsa.example.com/")
    with pytest.raises(TimestampClientError, match="PRODUCTION-DEFERRED"):
        await c.request_timestamp(_VALID_HASH)


# ---------------------------------------------------------------------------
# verify_timestamp_response edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_returns_false_for_wrong_key_length():
    """A non-32-byte 'public key' fails verification before any crypto op."""
    client = MockTimestampClient()
    response = await client.request_timestamp(_VALID_HASH)
    assert not verify_timestamp_response(response, tsa_public_key=b"\x00" * 16)


@pytest.mark.asyncio
async def test_verify_returns_false_for_empty_key():
    """Defensive: 0-byte key fails the length check, not the crypto."""
    client = MockTimestampClient()
    response = await client.request_timestamp(_VALID_HASH)
    assert not verify_timestamp_response(response, tsa_public_key=b"")


def test_verify_subclass_abstract_method_must_be_implemented():
    """TimestampClient is abstract - direct instantiation raises."""
    with pytest.raises(TypeError):
        TimestampClient()  # type: ignore[abstract]

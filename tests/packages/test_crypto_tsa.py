"""Tests for packages.crypto.tsa (CP9.19 / BR-06)."""

from __future__ import annotations

import json
import os
import pathlib
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
    verify_rfc3161_timestamp_response,
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
# Rfc3161TimestampClient - real RFC 3161 over HTTP
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


def test_rfc3161_client_identifier_derived_from_hostname():
    """Default identifier comes from the URL hostname."""
    c = Rfc3161TimestampClient(endpoint_url="https://freetsa.org/tsr")
    assert c.identifier == "freetsa.org"


def test_rfc3161_client_identifier_override():
    c = Rfc3161TimestampClient(
        endpoint_url="https://freetsa.org/tsr",
        identifier="custom-tsa",
    )
    assert c.identifier == "custom-tsa"


def test_rfc3161_client_default_timeout():
    """Default timeout is 30s per DEFAULT_TIMEOUT_SECONDS."""
    c = Rfc3161TimestampClient(endpoint_url="https://tsa.example.com/")
    assert c._timeout_seconds == Rfc3161TimestampClient.DEFAULT_TIMEOUT_SECONDS


def test_rfc3161_client_custom_timeout():
    c = Rfc3161TimestampClient(
        endpoint_url="https://tsa.example.com/",
        timeout_seconds=5.0,
    )
    assert c._timeout_seconds == 5.0


@pytest.mark.asyncio
async def test_rfc3161_client_rejects_short_hash():
    """Same shape-validation as the mock: 64 lowercase hex required."""
    c = Rfc3161TimestampClient(endpoint_url="https://tsa.example.com/")
    with pytest.raises(TimestampClientError, match="64 lowercase hex"):
        await c.request_timestamp("too-short")


@pytest.mark.asyncio
async def test_rfc3161_client_rejects_uppercase_hash():
    c = Rfc3161TimestampClient(endpoint_url="https://tsa.example.com/")
    with pytest.raises(TimestampClientError, match="64 lowercase hex"):
        await c.request_timestamp("A" * 64)


@pytest.mark.asyncio
async def test_rfc3161_client_maps_oserror_to_client_error(monkeypatch):
    """Network failure surfaces as TimestampClientError, not bare OSError.

    Callers map TimestampClientError to a "TSA unavailable; retry tomorrow"
    tombstone in the anchor ledger. Bare OSError would crash the anchor
    worker. We patch urllib.request.urlopen to raise.
    """
    import urllib.request

    def boom(*args, **kwargs):
        raise OSError("network unreachable")

    monkeypatch.setattr(urllib.request, "urlopen", boom)

    c = Rfc3161TimestampClient(endpoint_url="https://tsa.example.com/")
    with pytest.raises(TimestampClientError, match="HTTP transport error"):
        await c.request_timestamp(_VALID_HASH)


@pytest.mark.asyncio
async def test_rfc3161_client_maps_non_zero_status_to_client_error(monkeypatch):
    """A TSR with status != 0 (rejection) surfaces as TimestampClientError.

    We build a real-but-rejection TimeStampResp by mocking decode to return
    an object with status=2 (rejection). The caller must NOT treat this as
    success.
    """
    import urllib.request

    import rfc3161_client

    class _FakeHttpResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def read(self):
            return b"dummy response bytes"

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: _FakeHttpResp())

    class _FakeTsResp:
        status = 2  # rejection

    monkeypatch.setattr(
        rfc3161_client,
        "decode_timestamp_response",
        lambda data: _FakeTsResp(),
    )

    c = Rfc3161TimestampClient(endpoint_url="https://tsa.example.com/")
    with pytest.raises(TimestampClientError, match="status=2"):
        await c.request_timestamp(_VALID_HASH)


@pytest.mark.asyncio
async def test_rfc3161_client_maps_decode_failure_to_client_error(monkeypatch):
    """Garbage from the TSA surfaces as TimestampClientError, not bare exception."""
    import urllib.request

    import rfc3161_client

    class _FakeHttpResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def read(self):
            return b"not valid DER"

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: _FakeHttpResp())

    def _raise(data):
        raise ValueError("invalid ASN.1 input")

    monkeypatch.setattr(rfc3161_client, "decode_timestamp_response", _raise)

    c = Rfc3161TimestampClient(endpoint_url="https://tsa.example.com/")
    with pytest.raises(TimestampClientError, match="failed to decode TimeStampResp"):
        await c.request_timestamp(_VALID_HASH)


@pytest.mark.asyncio
async def test_rfc3161_client_happy_path_with_mocked_tsa(monkeypatch):
    """Full happy path with mocked HTTP + decode.

    Verifies: ASCII-encoded hex as imprint input, SHA-256 algorithm,
    POST to endpoint, status=0 success, genTime extracted, tsr_bytes
    preserved, signature = sha256(tsr_bytes).
    """
    import hashlib
    import urllib.request

    import rfc3161_client

    captured: dict[str, object] = {}

    class _FakeHttpResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def read(self):
            return b"FAKE_TSR_DER_BYTES"

    def _fake_urlopen(http_req, timeout=None):
        captured["url"] = http_req.full_url
        captured["method"] = http_req.get_method()
        captured["content_type"] = http_req.headers.get("Content-type")
        captured["data"] = http_req.data
        captured["timeout"] = timeout
        return _FakeHttpResp()

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    class _FakeTstInfo:
        gen_time = datetime(2026, 5, 15, 20, 0, 0, tzinfo=UTC)

    class _FakeTsResp:
        status = 0
        tst_info = _FakeTstInfo()

    monkeypatch.setattr(rfc3161_client, "decode_timestamp_response", lambda data: _FakeTsResp())

    c = Rfc3161TimestampClient(endpoint_url="https://freetsa.org/tsr", timeout_seconds=10.0)
    response = await c.request_timestamp(_VALID_HASH)

    # POST went to the right place with the right content-type
    assert captured["url"] == "https://freetsa.org/tsr"
    assert captured["method"] == "POST"
    assert captured["content_type"] == "application/timestamp-query"
    assert captured["timeout"] == 10.0
    # The request payload is a non-empty DER blob (we don't assert exact
    # bytes - that's rfc3161-client's contract not ours - but it must be
    # non-empty and begin with 0x30 SEQUENCE).
    assert isinstance(captured["data"], bytes | bytearray)
    assert len(captured["data"]) > 0  # type: ignore[arg-type]
    assert captured["data"][0] == 0x30  # type: ignore[index]

    # Response shape
    assert response.tsa_identifier == "freetsa.org"
    assert response.hashed_root == _VALID_HASH
    assert response.tsr_bytes == b"FAKE_TSR_DER_BYTES"
    assert response.timestamped_at == datetime(2026, 5, 15, 20, 0, 0, tzinfo=UTC)
    # signature = sha256(tsr_bytes)
    expected_sig = hashlib.sha256(b"FAKE_TSR_DER_BYTES").digest()
    assert response.signature == expected_sig


@pytest.mark.asyncio
async def test_rfc3161_client_attaches_utc_to_naive_gen_time(monkeypatch):
    """If the parser returned a naive datetime, force UTC (RFC 3161 mandates UTC)."""
    import urllib.request

    import rfc3161_client

    class _FakeHttpResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def read(self):
            return b"FAKE"

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: _FakeHttpResp())

    class _FakeTstInfo:
        gen_time = datetime(2026, 5, 15, 20, 0, 0)  # naive!

    class _FakeTsResp:
        status = 0
        tst_info = _FakeTstInfo()

    monkeypatch.setattr(rfc3161_client, "decode_timestamp_response", lambda data: _FakeTsResp())

    c = Rfc3161TimestampClient(endpoint_url="https://tsa.example.com/")
    response = await c.request_timestamp(_VALID_HASH)
    assert response.timestamped_at.tzinfo == UTC


@pytest.mark.asyncio
async def test_rfc3161_client_rejects_missing_tst_info(monkeypatch):
    """A TSR with status=0 but no embedded TSTInfo is malformed; surface as error."""
    import urllib.request

    import rfc3161_client

    class _FakeHttpResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def read(self):
            return b"FAKE"

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: _FakeHttpResp())

    class _FakeTsResp:
        status = 0
        tst_info = None

    monkeypatch.setattr(rfc3161_client, "decode_timestamp_response", lambda data: _FakeTsResp())

    c = Rfc3161TimestampClient(endpoint_url="https://tsa.example.com/")
    with pytest.raises(TimestampClientError, match="no TSTInfo"):
        await c.request_timestamp(_VALID_HASH)


# ---------------------------------------------------------------------------
# Rfc3161TimestampClient - LIVE integration tests (opt-in)
# ---------------------------------------------------------------------------
# These hit a real public TSA over the internet. Gated on FORENSA_USE_REAL_TSA_TESTS=1
# so CI doesn't hammer FreeTSA on every commit. Run locally with:
#   $env:FORENSA_USE_REAL_TSA_TESTS = '1'
#   poetry run pytest tests/packages/test_crypto_tsa.py -k live -v


@pytest.mark.asyncio
async def test_rfc3161_client_live_freetsa_end_to_end():
    """LIVE: hit FreeTSA, verify we get real DER + a sensible genTime."""
    import os

    if os.environ.get("FORENSA_USE_REAL_TSA_TESTS") != "1":
        pytest.skip("FORENSA_USE_REAL_TSA_TESTS not set; skipping live FreeTSA test")

    c = Rfc3161TimestampClient(endpoint_url="https://freetsa.org/tsr", timeout_seconds=30.0)
    response = await c.request_timestamp(_VALID_HASH)

    # Real DER starts with 0x30 SEQUENCE
    assert response.tsr_bytes[0] == 0x30
    # Real DER is sizeable (FreeTSA's TSRs are 4KB+)
    assert len(response.tsr_bytes) > 1000
    # genTime is tz-aware UTC and recent (within last 5 minutes)
    assert response.timestamped_at.tzinfo == UTC
    age = (datetime.now(UTC) - response.timestamped_at).total_seconds()
    assert -60 < age < 300, f"genTime suspiciously old/future: age={age}s"
    # Identifier defaulted to hostname
    assert response.tsa_identifier == "freetsa.org"
    # signature = sha256(tsr_bytes), 32 bytes
    assert len(response.signature) == 32


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


# ---------------------------------------------------------------------------
# verify_rfc3161_timestamp_response - PKIX cert-chain verification
# ---------------------------------------------------------------------------
# Bundled FreeTSA cert chain lives at tests/fixtures/freetsa/{tsa.crt,cacert.pem}.
# Live integration test (test_verify_rfc3161_against_live_freetsa_pkix_chain)
# is gated on FORENSA_USE_REAL_TSA_TESTS=1; unit tests use a synthetic
# TimestampResponse to exercise the input-validation paths.


_FIXTURES_DIR = pathlib.Path(__file__).parents[1] / "fixtures" / "freetsa"


def _read_freetsa_tsa_cert() -> bytes:
    return (_FIXTURES_DIR / "tsa.crt").read_bytes()


def _read_freetsa_root_cert() -> bytes:
    return (_FIXTURES_DIR / "cacert.pem").read_bytes()


def _make_mock_rfc3161_response() -> TimestampResponse:
    """A TimestampResponse with the shape Rfc3161TimestampClient produces,
    but tsr_bytes that won't decode as real DER. Used by paths that test
    failure modes before the cert/decode step."""
    return TimestampResponse(
        tsa_identifier="freetsa.org",
        tsr_bytes=b"\x30\x82\x00\x00",  # SEQUENCE header but invalid body
        timestamped_at=datetime.now(UTC),
        hashed_root=_VALID_HASH,
        signature=b"\x00" * 32,  # sha256 fingerprint placeholder
    )


def test_verify_rfc3161_returns_false_for_malformed_tsa_cert():
    """Garbage PEM in tsa_cert_pem surfaces as False, not an exception."""
    resp = _make_mock_rfc3161_response()
    assert not verify_rfc3161_timestamp_response(
        resp,
        tsa_cert_pem=b"not a real PEM",
        root_cert_pem=_read_freetsa_root_cert(),
    )


def test_verify_rfc3161_returns_false_for_malformed_root_cert():
    """Garbage PEM in root_cert_pem surfaces as False."""
    resp = _make_mock_rfc3161_response()
    assert not verify_rfc3161_timestamp_response(
        resp,
        tsa_cert_pem=_read_freetsa_tsa_cert(),
        root_cert_pem=b"not a real PEM",
    )


def test_verify_rfc3161_returns_false_for_malformed_intermediate_cert():
    """Garbage PEM in any intermediate surfaces as False."""
    resp = _make_mock_rfc3161_response()
    assert not verify_rfc3161_timestamp_response(
        resp,
        tsa_cert_pem=_read_freetsa_tsa_cert(),
        root_cert_pem=_read_freetsa_root_cert(),
        intermediate_cert_pems=[b"not a real PEM"],
    )


def test_verify_rfc3161_returns_false_for_garbage_tsr_bytes():
    """A TimestampResponse whose tsr_bytes don't decode as DER -> False."""
    resp = TimestampResponse(
        tsa_identifier="freetsa.org",
        tsr_bytes=b"this is definitely not asn1 der",
        timestamped_at=datetime.now(UTC),
        hashed_root=_VALID_HASH,
        signature=b"\x00" * 32,
    )
    assert not verify_rfc3161_timestamp_response(
        resp,
        tsa_cert_pem=_read_freetsa_tsa_cert(),
        root_cert_pem=_read_freetsa_root_cert(),
    )


def test_verify_rfc3161_returns_false_when_mock_tsr_bytes_used():
    """A MockTimestampClient produces JSON-shaped tsr_bytes, not DER.
    The PKIX verifier must return False (NOT crash) for these."""
    import asyncio

    async def _go() -> TimestampResponse:
        mc = MockTimestampClient()
        return await mc.request_timestamp(_VALID_HASH)

    mock_resp = asyncio.run(_go())
    assert not verify_rfc3161_timestamp_response(
        mock_resp,
        tsa_cert_pem=_read_freetsa_tsa_cert(),
        root_cert_pem=_read_freetsa_root_cert(),
    )


@pytest.mark.asyncio
async def test_verify_rfc3161_against_live_freetsa_pkix_chain():
    """LIVE: fetch a TSR from FreeTSA and PKIX-verify against the bundled
    cert chain in tests/fixtures/freetsa/. Proves the end-to-end story:

      Forensa -> Rfc3161TimestampClient -> FreeTSA -> TimestampResponse
      Regulator -> verify_rfc3161_timestamp_response -> True

    Gated on FORENSA_USE_REAL_TSA_TESTS=1 so CI doesn't hammer FreeTSA.
    """
    if os.environ.get("FORENSA_USE_REAL_TSA_TESTS") != "1":
        pytest.skip("FORENSA_USE_REAL_TSA_TESTS not set; skipping live PKIX test")

    client = Rfc3161TimestampClient(endpoint_url="https://freetsa.org/tsr", timeout_seconds=30.0)
    response = await client.request_timestamp(_VALID_HASH)

    # Positive: real TSR + correct cert chain -> True.
    assert verify_rfc3161_timestamp_response(
        response,
        tsa_cert_pem=_read_freetsa_tsa_cert(),
        root_cert_pem=_read_freetsa_root_cert(),
    )

    # Negative: tampered hashed_root -> False (imprint mismatch).
    tampered = TimestampResponse(
        tsa_identifier=response.tsa_identifier,
        tsr_bytes=response.tsr_bytes,
        timestamped_at=response.timestamped_at,
        hashed_root="0" * 64,  # wrong digest
        signature=response.signature,
    )
    assert not verify_rfc3161_timestamp_response(
        tampered,
        tsa_cert_pem=_read_freetsa_tsa_cert(),
        root_cert_pem=_read_freetsa_root_cert(),
    )

    # Negative: tampered tsr_bytes -> False (CMS decode/signature fails).
    tampered_tsr = TimestampResponse(
        tsa_identifier=response.tsa_identifier,
        tsr_bytes=response.tsr_bytes[:-4] + b"XXXX",  # corrupt last 4 bytes
        timestamped_at=response.timestamped_at,
        hashed_root=response.hashed_root,
        signature=response.signature,
    )
    assert not verify_rfc3161_timestamp_response(
        tampered_tsr,
        tsa_cert_pem=_read_freetsa_tsa_cert(),
        root_cert_pem=_read_freetsa_root_cert(),
    )

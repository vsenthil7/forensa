"""Tests for apps.api.auth.token — HmacBearerTokenVerifier + mint_hmac_token."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from apps.api.auth.token import (
    ExpiredTokenError,
    HmacBearerTokenVerifier,
    InvalidTokenError,
    mint_hmac_token,
)

_GOOD_SECRET = b"k" * 32  # 32 bytes, exactly the minimum


def _verifier_for(tenant_id: UUID, secret: bytes = _GOOD_SECRET) -> HmacBearerTokenVerifier:
    return HmacBearerTokenVerifier(tenant_id=tenant_id, secret=secret)


# ---------------------------------------------------------------------------
# Constructor: secret length enforcement
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_len", [0, 1, 16, 31])
def test_verifier_rejects_weak_secret(bad_len):
    with pytest.raises(ValueError, match="at least 32 bytes"):
        HmacBearerTokenVerifier(tenant_id=uuid4(), secret=b"x" * bad_len)


def test_verifier_accepts_32_byte_secret():
    """Lower-bound: exactly 32 bytes is accepted."""
    v = HmacBearerTokenVerifier(tenant_id=uuid4(), secret=b"x" * 32)
    assert v is not None


def test_verifier_accepts_long_secret():
    """64-byte secret (stronger than minimum) also accepted."""
    v = HmacBearerTokenVerifier(tenant_id=uuid4(), secret=b"y" * 64)
    assert v is not None


# ---------------------------------------------------------------------------
# mint_hmac_token roundtrip via verifier
# ---------------------------------------------------------------------------


def test_mint_and_verify_minimal_token_roundtrip():
    tid = uuid4()
    aid = uuid4()
    token = mint_hmac_token(
        tenant_id=tid,
        agent_id=aid,
        agent_slug="agent-roundtrip",
        secret=_GOOD_SECRET,
    )
    v = _verifier_for(tid)
    p = v.verify(token)
    assert p.tenant_id == tid
    assert p.agent_id == aid
    assert p.agent_slug == "agent-roundtrip"
    assert p.scopes == frozenset()


def test_mint_and_verify_with_scopes():
    tid = uuid4()
    token = mint_hmac_token(
        tenant_id=tid,
        agent_id=uuid4(),
        agent_slug="agent-scoped",
        secret=_GOOD_SECRET,
        scopes=["events:write", "receipts:read"],
    )
    p = _verifier_for(tid).verify(token)
    assert p.scopes == frozenset({"events:write", "receipts:read"})


def test_mint_and_verify_with_future_exp():
    tid = uuid4()
    future = (datetime.now(UTC) + timedelta(hours=1)).timestamp()
    token = mint_hmac_token(
        tenant_id=tid,
        agent_id=uuid4(),
        agent_slug="agent-exp",
        secret=_GOOD_SECRET,
        exp=future,
    )
    p = _verifier_for(tid).verify(token)
    assert p.agent_slug == "agent-exp"


def test_verify_token_with_past_exp_raises_expired():
    tid = uuid4()
    past = (datetime.now(UTC) - timedelta(hours=1)).timestamp()
    token = mint_hmac_token(
        tenant_id=tid,
        agent_id=uuid4(),
        agent_slug="agent-past",
        secret=_GOOD_SECRET,
        exp=past,
    )
    with pytest.raises(ExpiredTokenError, match="expired"):
        _verifier_for(tid).verify(token)


def test_mint_rejects_weak_secret():
    with pytest.raises(ValueError, match="at least 32 bytes"):
        mint_hmac_token(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            agent_slug="a",
            secret=b"short",
        )


# ---------------------------------------------------------------------------
# Verifier: invalid token shapes
# ---------------------------------------------------------------------------


def test_verify_rejects_token_without_dot():
    v = _verifier_for(uuid4())
    with pytest.raises(InvalidTokenError, match="shape"):
        v.verify("notatoken")


def test_verify_rejects_token_with_too_many_parts():
    v = _verifier_for(uuid4())
    with pytest.raises(InvalidTokenError, match="shape"):
        v.verify("a.b.c")


def test_verify_rejects_bad_base64url():
    v = _verifier_for(uuid4())
    # Python's urlsafe_b64decode silently drops chars outside the URL-safe
    # alphabet, so we trigger the decode-failure branch with a string that
    # raises binascii.Error('Incorrect padding') instead. 'abc!def' has
    # length 7 -> after padding restore the decoder sees something it can't
    # finish on.
    with pytest.raises(InvalidTokenError, match="base64url"):
        v.verify("abc!def.abc!def")


def test_verify_rejects_tampered_payload():
    """Same secret, but the payload was modified after MAC was computed."""
    tid = uuid4()
    token = mint_hmac_token(tenant_id=tid, agent_id=uuid4(), agent_slug="a", secret=_GOOD_SECRET)
    payload_b64, mac_b64 = token.split(".")
    # Flip a byte in the payload b64 by appending an extra char (encoded form
    # still decodes but the underlying bytes differ -> MAC mismatch).
    tampered = payload_b64 + "X" + "." + mac_b64
    with pytest.raises(InvalidTokenError, match="MAC verification failed"):
        _verifier_for(tid).verify(tampered)


def test_verify_rejects_wrong_secret():
    tid = uuid4()
    token = mint_hmac_token(tenant_id=tid, agent_id=uuid4(), agent_slug="a", secret=_GOOD_SECRET)
    other_secret = b"q" * 32
    v_with_other_secret = HmacBearerTokenVerifier(tenant_id=tid, secret=other_secret)
    with pytest.raises(InvalidTokenError, match="MAC verification failed"):
        v_with_other_secret.verify(token)


def test_verify_rejects_token_for_other_tenant():
    """Token minted for tenant A, presented to verifier configured for tenant B,
    but using the SAME secret (worst-case multi-tenant secret leak). The
    payload tenant_id check is the second wall."""
    tid_a = uuid4()
    tid_b = uuid4()
    token = mint_hmac_token(tenant_id=tid_a, agent_id=uuid4(), agent_slug="a", secret=_GOOD_SECRET)
    v_for_b = HmacBearerTokenVerifier(tenant_id=tid_b, secret=_GOOD_SECRET)
    with pytest.raises(InvalidTokenError, match="tenant_id does not match"):
        v_for_b.verify(token)


# ---------------------------------------------------------------------------
# Verifier: payload claim validation
# ---------------------------------------------------------------------------


def _build_token_with_payload(payload: object, secret: bytes = _GOOD_SECRET) -> str:
    """Build a syntactically valid token wrapping an arbitrary payload object.

    Used by negative tests that need a token whose MAC is correct but whose
    payload violates a claim-shape rule. Hand-rolls the encoding to skip
    mint_hmac_token's own input validation.
    """
    import hmac
    from hashlib import sha256

    payload_bytes = json.dumps(payload).encode("utf-8")
    mac = hmac.new(secret, payload_bytes, sha256).digest()
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).rstrip(b"=").decode("ascii")
    mac_b64 = base64.urlsafe_b64encode(mac).rstrip(b"=").decode("ascii")
    return f"{payload_b64}.{mac_b64}"


def test_verify_rejects_non_json_payload():
    """MAC over not-JSON bytes -> InvalidTokenError on JSON decode."""
    import hmac
    from hashlib import sha256

    raw_payload = b"\xff\xfe\xfd"  # not valid UTF-8 either
    mac = hmac.new(_GOOD_SECRET, raw_payload, sha256).digest()
    payload_b64 = base64.urlsafe_b64encode(raw_payload).rstrip(b"=").decode("ascii")
    mac_b64 = base64.urlsafe_b64encode(mac).rstrip(b"=").decode("ascii")
    token = f"{payload_b64}.{mac_b64}"

    v = _verifier_for(uuid4())
    with pytest.raises(InvalidTokenError, match="not valid JSON|payload"):
        v.verify(token)


def test_verify_rejects_payload_that_is_not_an_object():
    tid = uuid4()
    token = _build_token_with_payload([1, 2, 3])  # JSON array, not object
    with pytest.raises(InvalidTokenError, match="JSON object"):
        _verifier_for(tid).verify(token)


def test_verify_rejects_payload_missing_tenant_id():
    token = _build_token_with_payload({"agent_id": str(uuid4()), "agent_slug": "x"})
    with pytest.raises(InvalidTokenError, match="missing required claim"):
        _verifier_for(uuid4()).verify(token)


def test_verify_rejects_payload_with_malformed_uuid():
    token = _build_token_with_payload(
        {"tenant_id": "not-a-uuid", "agent_id": str(uuid4()), "agent_slug": "x"}
    )
    with pytest.raises(InvalidTokenError, match="missing required claim"):
        _verifier_for(uuid4()).verify(token)


def test_verify_rejects_empty_agent_slug():
    tid = uuid4()
    token = _build_token_with_payload(
        {"tenant_id": str(tid), "agent_id": str(uuid4()), "agent_slug": ""}
    )
    with pytest.raises(InvalidTokenError, match="non-empty"):
        _verifier_for(tid).verify(token)


def test_verify_rejects_non_string_agent_slug():
    tid = uuid4()
    token = _build_token_with_payload(
        {"tenant_id": str(tid), "agent_id": str(uuid4()), "agent_slug": 42}
    )
    with pytest.raises(InvalidTokenError, match="non-empty"):
        _verifier_for(tid).verify(token)


def test_verify_rejects_scopes_not_a_list():
    tid = uuid4()
    token = _build_token_with_payload(
        {
            "tenant_id": str(tid),
            "agent_id": str(uuid4()),
            "agent_slug": "x",
            "scopes": "not-a-list",
        }
    )
    with pytest.raises(InvalidTokenError, match="list of strings"):
        _verifier_for(tid).verify(token)


def test_verify_rejects_scopes_with_non_string_member():
    tid = uuid4()
    token = _build_token_with_payload(
        {
            "tenant_id": str(tid),
            "agent_id": str(uuid4()),
            "agent_slug": "x",
            "scopes": ["read", 42],
        }
    )
    with pytest.raises(InvalidTokenError, match="list of strings"):
        _verifier_for(tid).verify(token)


def test_verify_rejects_non_numeric_exp():
    tid = uuid4()
    token = _build_token_with_payload(
        {
            "tenant_id": str(tid),
            "agent_id": str(uuid4()),
            "agent_slug": "x",
            "exp": "not-a-timestamp",
        }
    )
    with pytest.raises(InvalidTokenError, match="exp must be a number"):
        _verifier_for(tid).verify(token)

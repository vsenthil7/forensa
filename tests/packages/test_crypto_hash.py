"""Tests for packages/crypto/hash.py - 100% branch coverage.

16 unit tests + 3 hypothesis property tests covering:
- canonical_json determinism + key ordering + UTF-8
- _normalise branches: None, naive datetime, tz-aware datetime, bytes,
  set, frozenset, dict, list, tuple, str/int/float/bool, unsupported type
- sha256_hex / sha256_bytes correctness + consistency
"""

from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime, timezone

import pytest
from hypothesis import given
from hypothesis import strategies as st

from packages.crypto.hash import _normalise as _norm
from packages.crypto.hash import (
    canonical_json,
    sha256_bytes,
    sha256_hex,
)

# ---------- canonical_json ----------


def test_canonical_json_returns_bytes():
    out = canonical_json({"a": 1})
    assert isinstance(out, bytes)
    assert out == b'{"a":1}'


def test_canonical_json_sorts_keys_deterministic():
    left = canonical_json({"b": 2, "a": 1, "c": 3})
    right = canonical_json({"a": 1, "c": 3, "b": 2})
    assert left == right == b'{"a":1,"b":2,"c":3}'


def test_canonical_json_no_whitespace():
    out = canonical_json({"a": [1, 2, 3], "b": {"nested": True}})
    assert b" " not in out
    assert out == b'{"a":[1,2,3],"b":{"nested":true}}'


def test_canonical_json_utf8_non_ascii_preserved():
    out = canonical_json({"name": "Sen\u00e9thil"})
    # ensure_ascii=False so the original UTF-8 bytes flow through
    assert "Sen\u00e9thil".encode() in out


# ---------- _normalise branch coverage ----------


def test_normalise_none_raises():
    with pytest.raises(ValueError, match="None is not a permissible"):
        _norm(None)


def test_normalise_naive_datetime_raises():
    with pytest.raises(ValueError, match="datetime must be timezone-aware"):
        _norm(datetime(2026, 5, 13, 14, 0))


def test_normalise_aware_datetime_returns_iso():
    dt = datetime(2026, 5, 13, 14, 0, tzinfo=UTC)
    assert _norm(dt) == "2026-05-13T14:00:00+00:00"


def test_normalise_aware_datetime_non_utc_tz():
    from datetime import timedelta

    tz = timezone(timedelta(hours=5, minutes=30))
    dt = datetime(2026, 5, 13, 14, 0, tzinfo=tz)
    assert _norm(dt).endswith("+05:30")


def test_normalise_bytes_base64_prefixed():
    raw = b"\x00\x01\x02hello"
    out = _norm(raw)
    assert out.startswith("base64:")
    assert base64.b64decode(out[len("base64:"):]) == raw


def test_normalise_set_returns_sorted_list():
    assert _norm({"c", "a", "b"}) == ["a", "b", "c"]


def test_normalise_frozenset_returns_sorted_list():
    assert _norm(frozenset({3, 1, 2})) == [1, 2, 3]


def test_normalise_dict_stringifies_keys_and_recurses():
    assert _norm({1: "x", "k": [10, 20]}) == {"1": "x", "k": [10, 20]}


def test_normalise_list_recurses():
    assert _norm([1, "a", True]) == [1, "a", True]


def test_normalise_tuple_recurses_to_list():
    assert _norm((1, "a", False)) == [1, "a", False]


@pytest.mark.parametrize(
    "value",
    ["text", 42, 3.14, True, False],
)
def test_normalise_primitives_pass_through(value):
    assert _norm(value) == value


def test_normalise_unsupported_type_raises():
    class Custom:
        pass

    with pytest.raises(TypeError, match="unsupported type"):
        _norm(Custom())


# ---------- sha256_hex / sha256_bytes ----------


def test_sha256_hex_known_value():
    # SHA-256 of canonical_json({"a":1}) == sha256(b'{"a":1}')
    expected = hashlib.sha256(b'{"a":1}').hexdigest()
    assert sha256_hex({"a": 1}) == expected


def test_sha256_bytes_is_32_bytes_and_matches_hex():
    payload = {"x": [1, 2, 3], "y": "string"}
    raw = sha256_bytes(payload)
    assert isinstance(raw, bytes)
    assert len(raw) == 32
    assert raw.hex() == sha256_hex(payload)


# ---------- Hypothesis property tests ----------


_json_primitives = st.one_of(
    st.text(max_size=20),
    st.integers(min_value=-(2**31), max_value=2**31 - 1),
    st.floats(allow_nan=False, allow_infinity=False, width=32),
    st.booleans(),
)


@given(
    st.dictionaries(
        keys=st.text(min_size=1, max_size=10),
        values=_json_primitives,
        max_size=8,
    )
)
def test_canonical_json_deterministic_property(payload):
    """Same input bytes-equal output across repeated calls."""
    assert canonical_json(payload) == canonical_json(payload)


@given(
    st.dictionaries(
        keys=st.text(min_size=1, max_size=10),
        values=_json_primitives,
        max_size=8,
    )
)
def test_sha256_hex_deterministic_property(payload):
    """SHA-256 hex is stable across repeated calls on the same payload."""
    assert sha256_hex(payload) == sha256_hex(payload)


@given(
    st.dictionaries(
        keys=st.text(min_size=1, max_size=10),
        values=_json_primitives,
        max_size=8,
    )
)
def test_sha256_hex_matches_canonical_json_hash(payload):
    """sha256_hex(p) == hexdigest(canonical_json(p)) for any valid payload."""
    assert sha256_hex(payload) == hashlib.sha256(canonical_json(payload)).hexdigest()

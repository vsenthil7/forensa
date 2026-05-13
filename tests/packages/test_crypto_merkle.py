"""Tests for packages/crypto/merkle.py - 100% branch coverage.

Unit tests + hypothesis property tests covering:
- entry_hash: deterministic bind over (sequence, payload_hash, prev_hash)
- next_entry: genesis branch + linked branch + sequence increment + prev_hash linkage
- next_entry: rejects bad payload_hash (non-str, empty)
- verify_chain: empty list = valid; single entry; multi-entry valid; tampered each field
- ChainError: missing keys, non-dict
- Property: arbitrary-length chain built via next_entry always verifies
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from packages.crypto.hash import sha256_hex
from packages.crypto.merkle import (
    ChainError,
    entry_hash,
    next_entry,
    verify_chain,
)

# ---------- entry_hash ----------


def test_entry_hash_is_canonical_sha256_hex():
    entry = {"sequence": 0, "payload_hash": "a" * 64, "prev_hash": None}
    # Genesis None prev_hash is bound as the empty-string sentinel so
    # canonical_json (which forbids None) can hash it deterministically.
    expected = sha256_hex({"sequence": 0, "payload_hash": "a" * 64, "prev_hash": ""})
    assert entry_hash(entry) == expected


def test_entry_hash_ignores_extra_fields():
    a = {"sequence": 1, "payload_hash": "b" * 64, "prev_hash": "x" * 64}
    b = {**a, "entry_hash": "ignored", "extra": "field"}
    assert entry_hash(a) == entry_hash(b)


def test_entry_hash_rejects_non_dict():
    with pytest.raises(ChainError, match="entry must be a dict"):
        entry_hash("not a dict")  # type: ignore[arg-type]


def test_entry_hash_rejects_missing_keys():
    with pytest.raises(ChainError, match="missing required keys"):
        entry_hash({"sequence": 0})


# ---------- next_entry: genesis ----------


def test_next_entry_genesis_has_sequence_zero_and_none_prev():
    e = next_entry(None, "a" * 64)
    assert e["sequence"] == 0
    assert e["prev_hash"] is None
    assert e["payload_hash"] == "a" * 64
    assert e["entry_hash"] == entry_hash(e)


# ---------- next_entry: linked ----------


def test_next_entry_links_to_previous():
    g = next_entry(None, "a" * 64)
    e1 = next_entry(g, "b" * 64)
    assert e1["sequence"] == 1
    assert e1["prev_hash"] == g["entry_hash"]
    assert e1["payload_hash"] == "b" * 64
    assert e1["entry_hash"] == entry_hash(e1)


def test_next_entry_increments_sequence_across_chain():
    chain = [next_entry(None, "h0" + "0" * 62)]
    for i in range(1, 5):
        chain.append(next_entry(chain[-1], f"h{i}" + "0" * 62))
    assert [e["sequence"] for e in chain] == [0, 1, 2, 3, 4]


# ---------- next_entry: rejections ----------


def test_next_entry_rejects_non_string_payload_hash():
    with pytest.raises(ChainError, match="non-empty string"):
        next_entry(None, 12345)  # type: ignore[arg-type]


def test_next_entry_rejects_empty_payload_hash():
    with pytest.raises(ChainError, match="non-empty string"):
        next_entry(None, "")


def test_next_entry_rejects_prev_entry_missing_keys():
    bad_prev = {"sequence": 0}  # missing entry_hash
    with pytest.raises(ChainError, match="missing required keys"):
        next_entry(bad_prev, "a" * 64)


# ---------- verify_chain ----------


def test_verify_chain_empty_is_valid():
    assert verify_chain([]) is True


def test_verify_chain_single_genesis_is_valid():
    g = next_entry(None, "a" * 64)
    assert verify_chain([g]) is True


def test_verify_chain_multi_valid():
    chain = [next_entry(None, "h0" + "0" * 62)]
    for i in range(1, 5):
        chain.append(next_entry(chain[-1], f"h{i}" + "0" * 62))
    assert verify_chain(chain) is True


def test_verify_chain_rejects_wrong_sequence():
    g = next_entry(None, "a" * 64)
    e1 = next_entry(g, "b" * 64)
    e1["sequence"] = 5  # tamper
    assert verify_chain([g, e1]) is False


def test_verify_chain_rejects_tampered_payload_hash():
    g = next_entry(None, "a" * 64)
    e1 = next_entry(g, "b" * 64)
    e1["payload_hash"] = "c" * 64  # tamper; entry_hash no longer matches
    assert verify_chain([g, e1]) is False


def test_verify_chain_rejects_broken_prev_link():
    g = next_entry(None, "a" * 64)
    e1 = next_entry(g, "b" * 64)
    e1["prev_hash"] = "z" * 64  # break the link
    assert verify_chain([g, e1]) is False


def test_verify_chain_rejects_tampered_entry_hash():
    g = next_entry(None, "a" * 64)
    g["entry_hash"] = "0" * 64  # entry_hash no longer matches recompute
    assert verify_chain([g]) is False


def test_verify_chain_rejects_genesis_with_non_none_prev_hash():
    g = next_entry(None, "a" * 64)
    g["prev_hash"] = "x" * 64
    # also rebind entry_hash so the entry_hash check passes but prev_hash check fails
    g["entry_hash"] = entry_hash(g)
    assert verify_chain([g]) is False


def test_verify_chain_rejects_malformed_entry():
    assert verify_chain([{"sequence": 0}]) is False


def test_verify_chain_rejects_non_dict_entry():
    assert verify_chain(["not a dict"]) is False  # type: ignore[list-item]


# ---------- Hypothesis property tests ----------


@given(st.lists(st.text(min_size=1, max_size=20), min_size=0, max_size=12))
def test_chain_built_via_next_entry_always_verifies(payload_hashes):
    """Any chain built sequentially via next_entry passes verify_chain."""
    chain: list[dict] = []
    prev: dict | None = None
    for ph in payload_hashes:
        e = next_entry(prev, ph)
        chain.append(e)
        prev = e
    assert verify_chain(chain) is True


@given(
    st.lists(st.text(min_size=1, max_size=20), min_size=2, max_size=6),
    st.integers(min_value=0),
)
def test_tampering_any_entry_breaks_verification(payload_hashes, tamper_pos_seed):
    """Mutating any entry in a non-trivial chain breaks verify_chain."""
    chain: list[dict] = []
    prev: dict | None = None
    for ph in payload_hashes:
        e = next_entry(prev, ph)
        chain.append(e)
        prev = e
    pos = tamper_pos_seed % len(chain)
    chain[pos]["payload_hash"] = "TAMPERED" * 8
    assert verify_chain(chain) is False

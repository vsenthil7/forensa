"""Append-only Merkle-style hash chain for Receipt linkage.

.. note:: **This module implements a Merkle hash _chain_, not a Merkle _tree_.**

   A chain gives O(N) inclusion proofs (prove receipt #N is in the chain by
   presenting all N entries). A true Merkle tree gives O(log N) inclusion
   proofs via sibling-hash paths to a tree root (RFC 6962-style certificate
   transparency is the canonical example).

   At hackathon-week scale (thousands of receipts per tenant) the chain is
   sufficient and correct. The tree upgrade is tracked as backlog item
   `NEW-P11.X.merkle-tree` in
   `docs/reviews/01_Rev_Claude_20260514_0919/REVIEW_RESPONSE_AND_BACKLOG_20260514_0955.md`
   and is required at 10M+ receipt scale for sub-linear inclusion proofs.

   The module name is left as ``merkle`` rather than renamed because (a)
   "Merkle-style hash chain" is established industry terminology (Sigstore,
   in-toto, AWS QLDB all use "Merkle" loosely) and (b) renaming would touch
   every import. This docstring is the honesty-fix per CP9.8 / NEW-P9.8.8.

The Forensa Receipt ledger is a per-tenant append-only sequence. Each Receipt
records prev_hash = receipt_hash of the previous entry, sequence = monotonic
counter starting at 0. Tampering with any entry invalidates the chain from
that point forward.

This module is the pure chain primitive: it knows nothing about Receipts,
tenants, or persistence. It operates on dict-shaped entries with the keys
sequence, payload_hash, prev_hash. It computes the next entry hash and
verifies an entire chain.

Contract:
- next_entry(prev_entry, payload) -> dict with sequence, payload_hash, prev_hash, entry_hash.
- entry_hash(entry) -> str: lowercase hex SHA-256 of the canonical bind.
- verify_chain(entries) -> bool: True iff the chain is self-consistent.

Bind formula:
  entry_hash = sha256_hex({
      "sequence": int,
      "payload_hash": str,
      "prev_hash": str | None,
  })
This is deterministic, canonical, and tamper-evident on all three fields.
"""

from __future__ import annotations

from typing import Any

from packages.crypto.hash import sha256_hex

# Genesis entry has no predecessor and sequence 0.
GENESIS_PREV_HASH: str | None = None
GENESIS_SEQUENCE = 0

# Sentinel string bound into the canonical SHA-256 input when prev_hash is None.
# canonical_json forbids None values; using a fixed sentinel keeps the bind
# deterministic without weakening the canonical-input contract.
_GENESIS_PREV_HASH_SENTINEL = ""


class ChainError(ValueError):
    """Raised when an entry is malformed or violates the chain contract."""


def entry_hash(entry: dict[str, Any]) -> str:
    """Return the canonical SHA-256 hex hash of a chain entry's bind fields.

    Only sequence, payload_hash, prev_hash are bound. entry_hash itself is
    excluded so that the hash is computed over the same field set whether
    or not entry_hash has already been assigned.
    """
    _require_keys(entry, ("sequence", "payload_hash", "prev_hash"))
    prev_hash = entry["prev_hash"]
    return sha256_hex(
        {
            "sequence": entry["sequence"],
            "payload_hash": entry["payload_hash"],
            "prev_hash": _GENESIS_PREV_HASH_SENTINEL if prev_hash is None else prev_hash,
        }
    )


def next_entry(prev_entry: dict[str, Any] | None, payload_hash: str) -> dict[str, Any]:
    """Build the next chain entry from the previous one and a new payload_hash.

    If prev_entry is None, this is the genesis entry (sequence 0, prev_hash None).
    Otherwise sequence = prev_entry["sequence"] + 1 and prev_hash = prev_entry["entry_hash"].

    Returns a fresh dict with sequence, payload_hash, prev_hash, entry_hash set.
    """
    if not isinstance(payload_hash, str) or not payload_hash:
        raise ChainError("payload_hash must be a non-empty string")

    if prev_entry is None:
        sequence = GENESIS_SEQUENCE
        prev_hash: str | None = GENESIS_PREV_HASH
    else:
        _require_keys(prev_entry, ("sequence", "entry_hash"))
        sequence = int(prev_entry["sequence"]) + 1
        prev_hash = prev_entry["entry_hash"]

    entry = {
        "sequence": sequence,
        "payload_hash": payload_hash,
        "prev_hash": prev_hash,
    }
    entry["entry_hash"] = entry_hash(entry)
    return entry


def verify_chain(entries: list[dict[str, Any]]) -> bool:
    """Return True iff the chain is self-consistent.

    Checks for every position i:
    - sequence == i
    - prev_hash equals entries[i-1]["entry_hash"] (or None at genesis)
    - entry_hash matches recompute over (sequence, payload_hash, prev_hash)

    Returns False on any structural failure, never raises ChainError.
    An empty list is considered a valid (trivially consistent) chain.
    """
    expected_prev_hash: str | None = GENESIS_PREV_HASH
    for i, entry in enumerate(entries):
        try:
            _require_keys(entry, ("sequence", "payload_hash", "prev_hash", "entry_hash"))
        except ChainError:
            return False
        if entry["sequence"] != i:
            return False
        if entry["prev_hash"] != expected_prev_hash:
            return False
        if entry_hash(entry) != entry["entry_hash"]:
            return False
        expected_prev_hash = entry["entry_hash"]
    return True


def _require_keys(entry: dict[str, Any], keys: tuple[str, ...]) -> None:
    if not isinstance(entry, dict):
        raise ChainError(f"entry must be a dict, got {type(entry).__name__}")
    missing = [k for k in keys if k not in entry]
    if missing:
        raise ChainError(f"entry missing required keys: {missing}")

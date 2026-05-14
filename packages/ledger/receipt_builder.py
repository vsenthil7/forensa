"""Receipt builder — produces fully-formed, signed Receipts from event payloads.

Pure construction layer. No DB, no async, no I/O. Given:
- event_id + event_payload
- the previous Receipt for this tenant (or None for genesis)
- a PolicySnapshot capturing the policy state at ingest
- the tenant's Ed25519 signing key

...produces a Receipt with:
- sequence = prev.sequence + 1 (or 0 at genesis)
- prev_receipt_hash = prev.receipt_hash (or None at genesis)
- payload_hash = sha256_hex(canonical_json(event_payload))
- receipt_hash = sha256_hex(canonical_json(bind fields))  -- the chain hash
- signature = Ed25519 over receipt_hash bytes

The bind fields used to compute receipt_hash are:
  {sequence, tenant_id, event_id, policy_bundle_id, policy_snapshot_id,
   payload_hash, prev_receipt_hash}

This is the chain Merkle-shape: tampering with ANY of those fields breaks
the recompute, and tampering with prev_receipt_hash also breaks the chain
linkage upstream.

The signature is over the canonical_json of the receipt_hash STRING (not the
hex bytes), so verification only needs (public_key, receipt_hash, signature).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from packages.crypto.hash import sha256_hex
from packages.crypto.sign import sign as ed25519_sign
from packages.crypto.sign import verify as ed25519_verify
from packages.policy.snapshot import PolicySnapshot
from packages.schema.receipt import Receipt


class ReceiptChainError(ValueError):
    """Raised when previous-receipt linkage is malformed."""


@dataclass(frozen=True)
class _BuildInputs:
    """Internal: validated inputs before binding."""

    tenant_id: UUID
    event_id: UUID
    policy_snapshot: PolicySnapshot
    policy_snapshot_id: UUID
    sequence: int
    prev_receipt_hash: str | None
    payload_hash: str


def build_receipt(
    *,
    tenant_id: UUID,
    event_id: UUID,
    event_payload: dict[str, Any],
    policy_snapshot: PolicySnapshot,
    policy_snapshot_id: UUID,
    prev_receipt: Receipt | None,
    tenant_signing_key: bytes,
    agent_signing_key: bytes | None = None,
) -> Receipt:
    """Build a signed Receipt for one event.

    prev_receipt is the most recently issued Receipt for this tenant, or
    None to start the chain. The returned Receipt is unwritten (the caller
    must persist it transactionally with the Event).

    Dual-signature contract (CP9.18 / BR-02):

    - ``signature`` is always the tenant signature over ``receipt_hash``.
    - ``agent_signature`` is the agent signature over the SAME
      ``receipt_hash``. Two independent witnesses to the same bound state.
    - When ``agent_signing_key`` is None, ``agent_signature`` is None on the
      returned Receipt. This is a transitional shape for backwards
      compatibility with receipts created before CP9.18; new ingest paths
      MUST supply an agent signing key.

    The two signatures sign the SAME 64 bytes of ``receipt_hash`` so each
    can be verified independently with its respective public key. Neither
    signature is part of the binding hash itself (that would be circular).
    The hash binds the content; the signatures are witnesses to the hash.
    """
    inputs = _validate_inputs(
        tenant_id=tenant_id,
        event_id=event_id,
        event_payload=event_payload,
        policy_snapshot=policy_snapshot,
        policy_snapshot_id=policy_snapshot_id,
        prev_receipt=prev_receipt,
    )

    receipt_hash = _compute_receipt_hash(inputs)
    signature = ed25519_sign(tenant_signing_key, receipt_hash)
    agent_signature: bytes | None = (
        ed25519_sign(agent_signing_key, receipt_hash) if agent_signing_key is not None else None
    )

    return Receipt(
        id=uuid4(),
        tenant_id=inputs.tenant_id,
        event_id=inputs.event_id,
        policy_bundle_id=inputs.policy_snapshot.policy_bundle_id,
        sequence=inputs.sequence,
        prev_receipt_hash=inputs.prev_receipt_hash,
        payload_hash=inputs.payload_hash,
        receipt_hash=receipt_hash,
        signature=signature,
        agent_signature=agent_signature,
        signed_at=datetime.now(UTC),
    )


def verify_receipt_signature(
    receipt: Receipt,
    tenant_public_key: bytes,
) -> bool:
    """Return True iff the receipt's TENANT signature verifies under the public key."""
    return ed25519_verify(tenant_public_key, receipt.receipt_hash, receipt.signature)


def verify_receipt_agent_signature(
    receipt: Receipt,
    agent_public_key: bytes,
) -> bool:
    """Return True iff the receipt's AGENT signature verifies under the public key.

    Returns False (NOT True) when ``receipt.agent_signature`` is None, even
    though there is technically nothing to disprove: callers checking dual
    signature coverage want a positive 'yes the agent signed this' answer.
    A backwards-compat receipt with no agent_signature is correctly reported
    as unverified at the agent layer.
    """
    if receipt.agent_signature is None:
        return False
    return ed25519_verify(agent_public_key, receipt.receipt_hash, receipt.agent_signature)


def recompute_receipt_hash(receipt: Receipt, policy_snapshot_id: UUID) -> str:
    """Recompute the canonical receipt_hash from a Receipt's bind fields.

    Used to verify a Receipt's tamper-evidence: the recomputed hash must
    equal receipt.receipt_hash. Caller supplies policy_snapshot_id because
    Receipt itself only holds policy_bundle_id; the snapshot id is on the
    ledger row.
    """
    bind = {
        "sequence": receipt.sequence,
        "tenant_id": str(receipt.tenant_id),
        "event_id": str(receipt.event_id),
        "policy_bundle_id": str(receipt.policy_bundle_id),
        "policy_snapshot_id": str(policy_snapshot_id),
        "payload_hash": receipt.payload_hash,
        "prev_receipt_hash": receipt.prev_receipt_hash or "",
    }
    return sha256_hex(bind)


# -------- internals --------


def _validate_inputs(
    *,
    tenant_id: UUID,
    event_id: UUID,
    event_payload: dict[str, Any],
    policy_snapshot: PolicySnapshot,
    policy_snapshot_id: UUID,
    prev_receipt: Receipt | None,
) -> _BuildInputs:
    if not isinstance(event_payload, dict):
        raise TypeError(f"event_payload must be a dict, got {type(event_payload).__name__}")

    payload_hash = sha256_hex(event_payload)

    if prev_receipt is None:
        sequence = 0
        prev_hash: str | None = None
    else:
        if prev_receipt.tenant_id != tenant_id:
            raise ReceiptChainError(
                f"prev_receipt.tenant_id {prev_receipt.tenant_id} does not "
                f"match tenant_id {tenant_id}; chains are per-tenant"
            )
        sequence = prev_receipt.sequence + 1
        prev_hash = prev_receipt.receipt_hash

    return _BuildInputs(
        tenant_id=tenant_id,
        event_id=event_id,
        policy_snapshot=policy_snapshot,
        policy_snapshot_id=policy_snapshot_id,
        sequence=sequence,
        prev_receipt_hash=prev_hash,
        payload_hash=payload_hash,
    )


def _compute_receipt_hash(inputs: _BuildInputs) -> str:
    """Compute the canonical SHA-256 of the bind fields.

    Genesis prev_hash is bound as the empty-string sentinel (consistent with
    packages.crypto.merkle's _GENESIS_PREV_HASH_SENTINEL) so canonical_json
    sees a string, not None.
    """
    bind = {
        "sequence": inputs.sequence,
        "tenant_id": str(inputs.tenant_id),
        "event_id": str(inputs.event_id),
        "policy_bundle_id": str(inputs.policy_snapshot.policy_bundle_id),
        "policy_snapshot_id": str(inputs.policy_snapshot_id),
        "payload_hash": inputs.payload_hash,
        "prev_receipt_hash": inputs.prev_receipt_hash or "",
    }
    return sha256_hex(bind)

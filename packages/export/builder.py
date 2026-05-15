"""Evidence pack builder (CP6.2).

Given a tenant, a window, and a list of Receipts + their policy_snapshot_ids,
compose an EvidencePack with PROV-O lineage and a root_hash that binds
the whole pack content. Pure function, no I/O.
"""

from __future__ import annotations

import base64
from datetime import datetime
from uuid import UUID, uuid4

from packages.crypto.hash import sha256_hex
from packages.export.schema import (
    AnchorEvidence,
    EvidencePack,
    EvidencePackHeader,
    ProvActivity,
    ReceiptEvidenceItem,
)
from packages.schema.receipt import Receipt


class EvidencePackError(ValueError):
    """Raised when inputs to build_evidence_pack are inconsistent."""


def _receipt_iri(rid: UUID) -> str:
    return f"urn:forensa:receipt:{rid}"


def _event_iri(eid: UUID) -> str:
    return f"urn:forensa:event:{eid}"


def _snapshot_iri(sid: UUID) -> str:
    return f"urn:forensa:snapshot:{sid}"


def _activity_iri() -> str:
    return f"urn:forensa:activity:{uuid4()}"


def build_evidence_pack(
    *,
    tenant_id: UUID,
    generated_at: datetime,
    scope_start: datetime,
    scope_end: datetime,
    receipts_with_snapshots: list[tuple[Receipt, UUID]],
    anchor: AnchorEvidence | None = None,
) -> EvidencePack:
    """Compose an EvidencePack from receipts and their snapshot ids.

    All receipts must belong to ``tenant_id``. The pack's root_hash is the
    SHA-256 of canonical_json over (header dict, receipts list, activities list,
    optional anchor dict) so any reordering or field tamper is detectable.

    Receipts are sorted by sequence ASC inside the pack so chain replay is
    direct: receipt[i+1].prev_receipt_hash == receipt[i].receipt_hash.

    The optional ``anchor`` parameter (CP9.23) embeds the day's RFC 3161 TSA
    proof. When provided, it MUST belong to ``tenant_id`` and is bound into
    root_hash so any subsequent tamper of the anchor data invalidates the
    pack. When None, the pack is anchor-less and the bind shape matches the
    pre-CP9.23 form.
    """
    if scope_end < scope_start:
        raise EvidencePackError("scope_end must be >= scope_start")
    for r, _ in receipts_with_snapshots:
        if r.tenant_id != tenant_id:
            raise EvidencePackError(
                f"receipt {r.id} belongs to tenant {r.tenant_id}, not {tenant_id}"
            )

    sorted_pairs = sorted(receipts_with_snapshots, key=lambda pair: pair[0].sequence)

    items: list[ReceiptEvidenceItem] = []
    activities: list[ProvActivity] = []
    for r, snap_id in sorted_pairs:
        items.append(
            ReceiptEvidenceItem(
                id=r.id,
                tenant_id=r.tenant_id,
                event_id=r.event_id,
                policy_bundle_id=r.policy_bundle_id,
                policy_snapshot_id=snap_id,
                sequence=r.sequence,
                prev_receipt_hash=r.prev_receipt_hash,
                payload_hash=r.payload_hash,
                receipt_hash=r.receipt_hash,
                signature_b64=base64.b64encode(r.signature).decode("ascii"),
                signed_at=r.signed_at,
            )
        )
        activities.append(
            ProvActivity(
                id=_activity_iri(),
                used_event=_event_iri(r.event_id),
                used_policy_snapshot=_snapshot_iri(snap_id),
                generated_receipt=_receipt_iri(r.id),
                started_at=r.signed_at,
                ended_at=r.signed_at,
            )
        )

    header = EvidencePackHeader(
        pack_id=uuid4(),
        tenant_id=tenant_id,
        generated_at=generated_at,
        scope_start=scope_start,
        scope_end=scope_end,
        receipt_count=len(items),
    )

    bind: dict[str, object] = {
        "header": header.model_dump(mode="json"),
        "receipts": [_canonicalise_item(it) for it in items],
        "activities": [a.model_dump(mode="json") for a in activities],
    }
    if anchor is not None:
        bind["anchor"] = _canonicalise_anchor(anchor)
    # NOTE (CP9.10, re review finding 3.17.5 RETRACTED): receipt_count IS
    # bound into root_hash because header.model_dump() includes it. The
    # reviewer flagged this as missing then retracted; this comment is here
    # so a future reader doesn't re-flag the same false positive.
    root_hash = sha256_hex(bind)

    return EvidencePack(
        header=header,
        receipts=items,
        activities=activities,
        anchor=anchor,
        root_hash=root_hash,
    )


def _canonicalise_item(it: ReceiptEvidenceItem) -> dict[str, object]:
    """Dump a ReceiptEvidenceItem with None prev_receipt_hash bound as "".

    canonical_json forbids None values. Genesis receipts carry
    prev_receipt_hash=None at the model level; bind it as empty-string
    sentinel here to keep the canonical hash stable.
    """
    d = it.model_dump(mode="json")
    if d.get("prev_receipt_hash") is None:
        d["prev_receipt_hash"] = ""
    return d


def _canonicalise_anchor(anchor: AnchorEvidence) -> dict[str, object]:
    """Dump an AnchorEvidence with Nones replaced by empty-string sentinels.

    canonical_json forbids None values. Deferred anchors carry None on
    four fields (root_hash, tsr_bytes_b64, tsa_signature_b64,
    timestamped_at). Bind them as empty-string sentinels so the canonical
    hash is stable and a deferred-anchor pack still produces a meaningful
    root_hash that the verifier can reproduce.
    """
    d = anchor.model_dump(mode="json")
    for k in ("root_hash", "tsr_bytes_b64", "tsa_signature_b64", "timestamped_at"):
        if d.get(k) is None:
            d[k] = ""
    return d


def verify_evidence_pack(pack: EvidencePack) -> bool:
    """Recompute root_hash from the pack content; True iff matches.

    Independent verifier a regulator can run on the JSON-LD wire form to
    confirm the pack has not been tampered with. The bind shape includes
    the optional ``anchor`` field iff present, matching the build path.
    """
    bind: dict[str, object] = {
        "header": pack.header.model_dump(mode="json"),
        "receipts": [_canonicalise_item(it) for it in pack.receipts],
        "activities": [a.model_dump(mode="json") for a in pack.activities],
    }
    if pack.anchor is not None:
        bind["anchor"] = _canonicalise_anchor(pack.anchor)
    return sha256_hex(bind) == pack.root_hash

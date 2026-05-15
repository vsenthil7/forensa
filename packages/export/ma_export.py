"""M&A due diligence export (CP9.28 / BR-13).

An M&A acquirer or their forensic accountant needs the full evidence trail
for a target's AI agent workload over a date range, packaged as a single
sealed deliverable suitable for inclusion in a virtual data room. The
deliverable is:

    MaDiligenceExport
      ├── header (tenant_id, scope_start, scope_end, generated_at,
      │           pack_count, total_receipt_count, anchor_count)
      ├── evidence_packs: list[EvidencePack]  (one per chunk)
      ├── anchor_proofs:  list[AnchorEvidence]
      └── ma_root_hash    SHA-256 over canonical_json of the above

The acquirer verifies the bundle's integrity by recomputing ma_root_hash
from the canonical bind shape. If it matches the published value, every
embedded EvidencePack's root_hash is also verifiable independently, and
every embedded anchor's TSR can be re-verified via openssl ts -verify
against the chain root recorded in the anchor.

Why chunking the scope window: a single EvidencePack is capped at 1000
receipts (_MAX_RECEIPTS_PER_PACK in routes/evidence.py). M&A scope
windows can span 12-24 months and tens of thousands of Receipts. The
exporter chunks the scope window by anchored day so each EvidencePack
fits under the cap AND each pack's root_hash is bound to exactly one
day's TSA anchor.

PRODUCTION-DEFERRED:
- NEW-P10.X.ma-export-encryption-at-rest: encrypt the bundle with the
  acquirer's public key so only they can decrypt it.
- (closed in CP9.34) NEW-P11.X.ma-export-detached-platform-signature:
  sign the bundle with Forensa's platform key so the acquirer can verify
  provenance. ``sign_ma_diligence_export`` + ``verify_ma_diligence_export_signature``
  below.
- NEW-P12.X.ma-export-streaming: today the full bundle is built in memory
  (~1-10 MB per 1000 receipts); for 100K+ receipt exports stream the
  bundle to S3 with multipart upload.
- NEW-P12.X.ma-export-async-job: today this is synchronous; for very
  large windows return a job_id and let the caller poll.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from packages.crypto.hash import sha256_hex
from packages.crypto.sign import sign as ed25519_sign
from packages.crypto.sign import verify as ed25519_verify
from packages.export.schema import AnchorEvidence, EvidencePack

_MAX_PACKS_PER_EXPORT = 366  # one year-worth of daily anchored packs
_MAX_TOTAL_RECEIPTS = 100_000  # hard ceiling on bundle size


class MaExportError(ValueError):
    """Raised when an M&A export cannot be assembled."""


class MaDiligenceHeader(BaseModel):
    """Manifest header for an M&A due diligence export."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    export_id: UUID = Field(..., description="UUID of this export bundle")
    tenant_id: UUID = Field(..., description="Target tenant whose evidence this is")
    generated_at: datetime = Field(..., description="UTC timestamp when the bundle was assembled")
    scope_start: datetime = Field(..., description="Inclusive start of M&A scope window")
    scope_end: datetime = Field(..., description="Inclusive end of M&A scope window")
    pack_count: int = Field(..., ge=0, description="Number of EvidencePacks in the bundle")
    anchor_count: int = Field(..., ge=0, description="Number of distinct TSA anchors in the bundle")
    total_receipt_count: int = Field(..., ge=0, description="Sum of receipt_count across packs")

    @field_validator("generated_at", "scope_start", "scope_end")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware (UTC)")
        return v


class MaDiligenceExport(BaseModel):
    """Sealed M&A due diligence bundle.

    `ma_root_hash` binds the canonical JSON of (header, evidence_packs,
    anchor_proofs) so the acquirer can verify the bundle's integrity
    independently of Forensa's API.

    CP9.34 / NEW-P11.X.ma-export-detached-platform-signature:
    ``platform_signature`` is an optional Ed25519 signature over the
    ``ma_root_hash`` string (bytes), produced by Forensa's platform key.
    The acquirer can verify it under Forensa's published platform public
    key, proving the bundle came from Forensa and was not forged in
    MaDiligenceExport shape by a third party. None = unsigned bundle
    (backwards compat with CP9.28 + CP9.30 bundles that pre-date this
    field).
    """

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    export_type: str = Field(default="forensa:MaDiligenceExport", alias="@type")
    header: MaDiligenceHeader
    evidence_packs: list[EvidencePack]
    anchor_proofs: list[AnchorEvidence]
    ma_root_hash: str = Field(..., min_length=64, max_length=64)
    platform_signature: bytes | None = Field(
        default=None,
        description=(
            "Optional Ed25519 signature over ma_root_hash by Forensa's platform key. "
            "None for unsigned bundles. 64 bytes when present."
        ),
    )
    platform_key_id: str | None = Field(
        default=None,
        max_length=128,
        description=(
            "Identifier for the Forensa platform key that produced platform_signature. "
            "None iff platform_signature is None. The acquirer uses this id to look up "
            "the published platform public key (e.g. via Forensa's JWKS endpoint or "
            "contractual cert distribution)."
        ),
    )

    @field_validator("ma_root_hash")
    @classmethod
    def _root_hex(cls, v: str) -> str:
        if not all(c in "0123456789abcdef" for c in v):
            raise ValueError("ma_root_hash must be lowercase hex")
        return v

    @field_validator("platform_signature", mode="before")
    @classmethod
    def _sig_accept_b64(cls, v: object) -> object:
        """Accept both raw 64-byte signatures (build path) and base64-encoded
        strings (deserialization path).

        When a signed MaDiligenceExport round-trips through JSON (CP9.44
        async-job result_export persistence, or any future S3 / email
        delivery), the bytes field is serialised as base64. The model
        must accept that string on the way back in and decode it to 64
        raw bytes. Existing build paths still pass raw bytes; this
        validator is a no-op for those.
        """
        if v is None:
            return None
        if isinstance(v, bytes):
            return v
        if isinstance(v, str):
            # base64 string; pad if needed (urlsafe and standard both work
            # for raw bytes since the Ed25519 signature won't ever contain
            # the +/-/= boundaries differently).
            import base64 as _b64

            padded = v + "=" * (-len(v) % 4)
            try:
                return _b64.b64decode(padded)
            except (ValueError, _b64.binascii.Error) as exc:  # type: ignore[attr-defined]
                raise ValueError(f"platform_signature is not valid base64: {exc}") from exc
        raise TypeError(f"platform_signature must be bytes or base64 str; got {type(v).__name__}")

    @field_validator("platform_signature")
    @classmethod
    def _sig_len(cls, v: bytes | None) -> bytes | None:
        if v is not None and len(v) != 64:
            raise ValueError(f"platform_signature must be 64 bytes Ed25519; got {len(v)}")
        return v

    @field_serializer("platform_signature", when_used="json")
    def _serialise_sig(self, v: bytes | None) -> str | None:
        """Base64-encode the signature for JSON serialisation.

        Pydantic v2's default bytes-to-JSON path tries `.decode('utf-8')`
        which fails for raw Ed25519 signature bytes (e.g. 0x93 is not a
        valid UTF-8 start byte). We override with standard b64 so the
        result is round-trippable: model_dump_json -> JSON -> model_validate
        recovers the original 64-byte signature via the `_sig_accept_b64`
        validator above.
        """
        if v is None:
            return None
        import base64 as _b64

        return _b64.b64encode(v).decode("ascii")


def build_ma_diligence_export(
    *,
    tenant_id: UUID,
    scope_start: datetime,
    scope_end: datetime,
    generated_at: datetime,
    evidence_packs: list[EvidencePack],
    anchor_proofs: list[AnchorEvidence],
) -> MaDiligenceExport:
    """Compose an M&A due diligence export from pre-built EvidencePacks + anchors.

    Caller is responsible for:
      - Chunking the scope window into per-day or per-N-receipt slices
        and building one EvidencePack per slice.
      - Collecting the distinct anchor rows that cover the scope window.

    The exporter validates:
      - All EvidencePacks belong to ``tenant_id``.
      - Pack count <= ``_MAX_PACKS_PER_EXPORT`` (366).
      - Total receipt count across packs <= ``_MAX_TOTAL_RECEIPTS`` (100K).
      - scope_end >= scope_start, both tz-aware.

    The output's ``ma_root_hash`` binds the header + every pack's
    root_hash + every anchor's anchor_id so any tamper of any included
    artefact invalidates the bundle.
    """
    if scope_start.tzinfo is None or scope_end.tzinfo is None:
        raise MaExportError("scope_start and scope_end must be timezone-aware (UTC)")
    if scope_end < scope_start:
        raise MaExportError("scope_end must be >= scope_start")
    if len(evidence_packs) > _MAX_PACKS_PER_EXPORT:
        raise MaExportError(f"too many packs: {len(evidence_packs)} > {_MAX_PACKS_PER_EXPORT}")
    total_receipts = sum(p.header.receipt_count for p in evidence_packs)
    if total_receipts > _MAX_TOTAL_RECEIPTS:
        raise MaExportError(
            f"bundle exceeds {_MAX_TOTAL_RECEIPTS} receipts ({total_receipts}); "
            "narrow the scope or split the export"
        )
    for p in evidence_packs:
        if p.header.tenant_id != tenant_id:
            raise MaExportError(
                f"pack {p.header.pack_id} belongs to tenant {p.header.tenant_id}, "
                f"not {tenant_id}"
            )

    header = MaDiligenceHeader(
        export_id=uuid4(),
        tenant_id=tenant_id,
        generated_at=generated_at,
        scope_start=scope_start,
        scope_end=scope_end,
        pack_count=len(evidence_packs),
        anchor_count=len(anchor_proofs),
        total_receipt_count=total_receipts,
    )

    # Bind ma_root_hash over:
    #   - header (binds scope window, counts, tenant id)
    #   - every pack's root_hash (binds each pack's full content via its
    #     own internal root_hash; we don't re-bind the full pack content
    #     because that would be redundant — pack.root_hash already covers it)
    #   - every anchor's anchor_id + root_hash (binds the TSA proofs)
    bind: dict[str, object] = {
        "header": header.model_dump(mode="json"),
        "pack_root_hashes": [p.root_hash for p in evidence_packs],
        "anchor_ids": sorted(str(a.anchor_id) for a in anchor_proofs),
        "anchor_root_hashes": [a.root_hash or "" for a in anchor_proofs],
    }
    ma_root_hash = sha256_hex(bind)

    return MaDiligenceExport(
        header=header,
        evidence_packs=evidence_packs,
        anchor_proofs=anchor_proofs,
        ma_root_hash=ma_root_hash,
    )


def verify_ma_diligence_export(export: MaDiligenceExport) -> bool:
    """Recompute ma_root_hash from the export content; True iff matches.

    Independent verifier the M&A acquirer can run on the bundle without
    contacting Forensa. Symmetric with build_ma_diligence_export's bind
    shape.
    """
    bind: dict[str, object] = {
        "header": export.header.model_dump(mode="json"),
        "pack_root_hashes": [p.root_hash for p in export.evidence_packs],
        "anchor_ids": sorted(str(a.anchor_id) for a in export.anchor_proofs),
        "anchor_root_hashes": [a.root_hash or "" for a in export.anchor_proofs],
    }
    return sha256_hex(bind) == export.ma_root_hash


def daily_chunks(scope_start: datetime, scope_end: datetime) -> list[tuple[datetime, datetime]]:
    """Yield (chunk_start, chunk_end) pairs covering the scope window day-by-day.

    Each pair represents one UTC day. The acquirer chunks the export per
    anchored day so each pack maps 1:1 with one TSA anchor. Helper used
    by the route layer; pure function for easy testing.
    """
    if scope_end < scope_start:
        raise MaExportError("scope_end must be >= scope_start")
    chunks: list[tuple[datetime, datetime]] = []
    cursor = scope_start
    while cursor < scope_end:
        next_day = cursor + timedelta(days=1)
        chunk_end = min(next_day, scope_end)
        chunks.append((cursor, chunk_end))
        cursor = next_day
    return chunks


# ---------------------------------------------------------------------------
# CP9.34 / NEW-P11.X.ma-export-detached-platform-signature
# ---------------------------------------------------------------------------
#
# An acquirer receiving a MaDiligenceExport JSON-LD blob over email, S3, or
# a virtual data room URL wants to prove TWO things:
#
#   (a) The bundle's content is internally consistent.
#       Solved by build_ma_diligence_export + verify_ma_diligence_export
#       (the ma_root_hash binds header + pack root_hashes + anchor proofs).
#
#   (b) The bundle came from Forensa, not a third party who happened to
#       construct a syntactically valid MaDiligenceExport.
#       Solved by the platform_signature field + the two functions below.
#       Forensa signs ma_root_hash with its platform Ed25519 key. The
#       acquirer verifies under the published platform public key.
#
# Why detached, not a separate envelope: the signature lives INSIDE the
# MaDiligenceExport JSON so a single artefact carries both the content
# and its provenance proof. Acquirers don't need to track two files.
#
# Forwards-compatibility: pre-CP9.34 bundles have platform_signature=None
# and platform_key_id=None, which the verifier reports as "unsigned" (False)
# rather than raising. This lets bundles generated by CP9.28 + CP9.30
# routes keep working through the file format upgrade.


class MaExportSignatureError(ValueError):
    """Raised when an M&A export cannot be signed (e.g. malformed key)."""


def sign_ma_diligence_export(
    export: MaDiligenceExport,
    *,
    platform_private_key: bytes,
    platform_key_id: str,
) -> MaDiligenceExport:
    """Return a copy of ``export`` with ``platform_signature`` populated.

    Signs ``export.ma_root_hash`` as raw UTF-8 bytes using the supplied
    Ed25519 private key. The returned MaDiligenceExport is identical to
    the input except for ``platform_signature`` (64 bytes) and
    ``platform_key_id`` (the supplied identifier).

    Parameters
    ----------
    export : MaDiligenceExport
        The bundle to sign. May or may not already be signed; this call
        replaces any prior signature unconditionally.
    platform_private_key : bytes
        32 bytes Ed25519 private key. In production this lives in Forensa's
        platform KMS / HSM; the bytes-in-process shape is a stub until
        NEW-P10.X.kms-adapter lands.
    platform_key_id : str
        Opaque identifier the acquirer uses to look up the matching public
        key. E.g. "forensa-platform-key-v1". Must be non-empty and at most
        128 chars.

    Returns
    -------
    MaDiligenceExport
        A new MaDiligenceExport with signature + key_id populated. The
        original export is not mutated (Pydantic frozen).

    Raises
    ------
    MaExportSignatureError
        If ``platform_private_key`` is not 32 bytes or ``platform_key_id``
        is empty.
    """
    if len(platform_private_key) != 32:
        raise MaExportSignatureError(
            f"platform_private_key must be 32 bytes Ed25519; got {len(platform_private_key)}"
        )
    if not platform_key_id or not platform_key_id.strip():
        raise MaExportSignatureError("platform_key_id must be non-empty")
    if len(platform_key_id) > 128:
        raise MaExportSignatureError(
            f"platform_key_id must be <= 128 chars; got {len(platform_key_id)}"
        )
    signature = ed25519_sign(platform_private_key, export.ma_root_hash)
    return export.model_copy(
        update={
            "platform_signature": signature,
            "platform_key_id": platform_key_id,
        }
    )


def verify_ma_diligence_export_signature(
    export: MaDiligenceExport,
    *,
    platform_public_key: bytes,
) -> bool:
    """Verify ``export.platform_signature`` against ``platform_public_key``.

    Returns False (NOT True) when ``export.platform_signature`` is None
    -- an unsigned bundle does NOT verify as "provenance from Forensa".
    Pre-CP9.34 bundles report as unsigned without raising; acquirers can
    distinguish "signed but invalid" (returns False AND signature is
    non-None) from "unsigned" (returns False AND signature is None).

    Non-raising: returns False on any verification failure including
    malformed public key length. Safe to call on attacker-controlled
    bundles.

    Parameters
    ----------
    export : MaDiligenceExport
        The bundle to verify.
    platform_public_key : bytes
        32 bytes Ed25519 public key. The acquirer obtains this from
        Forensa's published JWKS endpoint, certificate distribution, or
        contractual exchange. The key_id on ``export.platform_key_id``
        identifies which key to look up.

    Returns
    -------
    bool
        True iff the signature verifies and the key is well-formed and
        a signature is actually present.
    """
    if export.platform_signature is None:
        return False
    if len(platform_public_key) != 32:
        return False
    return ed25519_verify(
        platform_public_key,
        export.ma_root_hash,
        export.platform_signature,
    )

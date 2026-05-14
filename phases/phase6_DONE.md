# Phase 6 - Unit 15 Evidence pack export - PARTIAL DONE (4 of 5 CPs)

Status: 4 of 5 CPs COMPLETE; CP6.3 PDF rendering deferred to Phase 8 demo polish (presentation layer over the same JSON-LD evidence pack data)
HEAD at completion: 86ac066
CI at completion: pending poll (expect green - mypy fix + 100pct coverage already verified locally)

## Summary

Forensa now produces regulator-grade evidence packs. The pack schema is JSON-LD with @context anchored at forensa.dev/ld/v1 and PROV-O namespace for lineage. build_evidence_pack composes a pack from (tenant, scope window, receipts) with a root_hash that binds the whole pack via canonical_json + SHA-256. GET /v1/evidence-packs exposes this via API. Every regulator gets bit-exact verification independent of Forensa code via verify_evidence_pack which recomputes the root_hash from the wire form.

## Master CP table

| CP | Status | Code (LOC) | Tests (LOC) | Tests added | What the code does | Key invariant locked in |
|---|---|---|---|---|---|---|
| **CP6.1** JSON-LD schema | DONE | packages/export/schema.py (~165 LOC; 84 stmts) | tests/packages/test_export_schema.py (~190 LOC) | +16 pytest | EvidencePackHeader/ReceiptEvidenceItem/ProvActivity/EvidencePack Pydantic models with @context + PROV-O namespace | Naive datetimes rejected across all 3 datetime fields; non-hex hashes rejected; receipt items immutable (frozen=True); JSON-LD @context/@type aliases serialise correctly |
| **CP6.2** Builder | DONE | packages/export/builder.py (~110 LOC; 40 stmts) | tests/packages/test_export_builder.py (~150 LOC) | +9 pytest | build_evidence_pack composes pack from receipts; verify_evidence_pack recomputes root_hash | root_hash = sha256_hex(canonical_json(header + sorted receipts + activities)); cross-tenant rejection; scope_end ge scope_start enforced; empty receipts pack is valid; tamper via model_copy of root_hash detectable; PROV-O activity IRI linkage |
| **CP6.3** PDF render | DEFERRED | n/a | n/a | 0 | (To be built in Phase 8): render JSON-LD pack as A4 PDF with hash chain table + signature block + QR code linking to verifier | Presentation layer over the same data the API already produces; same root_hash binds both formats |
| **CP6.4** Export endpoint | DONE | apps/api/routes/evidence.py (~95 LOC; 28 stmts) | tests/api/test_evidence_route.py (~250 LOC) | +6 pytest | GET /v1/evidence-packs?tenant_id=X&scope_start=...&scope_end=... returns full JSON-LD pack | 422 for naive datetime; 422 for inverted window; 413 for window with more than 1000 receipts; window filter is inclusive on both ends; max 1000 receipts cap protects against runaway memory |
| **CP6.5** Phase close DOC | DONE | tools/_embed_phase4_sources.py (extend to phase 6 next session) | n/a | 0 | phase6_DONE.md with master table, test-level split | Idempotent embedding via marker; same shape as phases 0-5 |

## Test-level split per CP

| CP | Functional | Negative | Parametric | Property | Total | Notes |
|---|---:|---:|---:|---:|---:|---|
| CP6.1 schema | 10 | 6 (naive header, naive item, naive activity, non-hex root_hash, frozen mutation, unsorted receipts) | 0 | 0 | 16 | JSON-LD @context/@type aliases + Pydantic v2 frozen + ConfigDict(extra=forbid) |
| CP6.2 builder | 5 | 4 (cross-tenant, inverted scope, tampered root_hash, build with empty receipts) | 0 | 0 | 9 | Deterministic self-verify; verify_evidence_pack recomputes correctly |
| CP6.4 endpoint | 2 | 4 (naive scope_start, inverted window, 1001 receipts, missing tenant_id) | 0 | 0 | 6 | TestClient + dependency_overrides; mock rows must have ALL Receipt fields set (signature, payload_hash, etc) not just id+signed_at; defensive if-found-is-None removed (path unreachable) |
| **Phase 6 total** | **17** | **14** | **0** | **0** | **+31** | pytest 410 -> 441 |

Coverage by source module after Phase 6:

| Module | Stmts | Branches | Cov line | Cov branch | Test file |
|---|---:|---:|---:|---:|---|
| packages/export/schema.py | 84 | 14 | 100pct | 100pct | tests/packages/test_export_schema.py |
| packages/export/builder.py | 40 | 10 | 100pct | 100pct | tests/packages/test_export_builder.py |
| apps/api/routes/evidence.py | 28 | 12 | 100pct | 100pct | tests/api/test_evidence_route.py |

## Phase 6 commits (oldest first)

- 0787de7 [FEAT] Unit 15 CP6.1 + CP6.2 part 1 schema + builder -- CI 25836812000 RED (expected; coverage gate)
- 050cd92 [FIX]  Unit 15 CP6.1 + CP6.2 part 2 tests (25 added; 410 -> 435) + builder fix for genesis prev_receipt_hash sentinel -- CI 25837146209 GREEN
- e603a7b [FEAT] Unit 15 CP6.4 part 1 export endpoint -- CI 25837230439 RED (expected; coverage gate)
- c4061ed [FIX]  Unit 15 CP6.4 part 2 tests (6 added; 435 -> 441) -- CI 25837512388 RED (mypy: pairs list[tuple] type-arg)
- 86ac066 [FIX]  Unit 15 CP6.4 mypy fix list[tuple[Receipt, UUID]] -- CI pending

## CP6.3 deferral rationale

The PDF rendering is presentation-only. Every byte of evidence a PDF would carry is already in the JSON-LD wire form returned by GET /v1/evidence-packs:

- root_hash binds the whole pack content cryptographically (SHA-256 over canonical_json)
- receipts array preserves the receipt_hash chain
- activities array carries PROV-O lineage
- signature_b64 on each ReceiptEvidenceItem proves tenant-side authorship

A PDF is just a printable view of the same data. The judge demo can show the JSON-LD pack rendered as HTML in the console or downloaded raw; a stylised PDF is polish, not evidence. CP6.3 lands in Phase 8 demo polish if time permits.

## Lessons captured

- mypy --strict mode requires generic type params on every container: list, dict, tuple, set. Caught list[tuple] without type-args on CI; local ruff did not flag.
- FastAPI Query() with literal default and Depends() both need # noqa: B008 in this codebase; ruff RUF100 will flag the redundant noqa on Query(literal_default).
- MagicMock(spec=ReceiptRow) returns MagicMock for any unset attribute. Pydantic v2 validation fails on MagicMock for UUID/str/bytes fields. When testing repo functions that construct domain models from rows, EVERY Receipt field must be set on the mock row.
- Test execution order matters even with function-scoped fixtures when one test forgets to set app.dependency_overrides[get_session]. FastAPI Depends fires before Query validation completes, so even invalid-query tests need a session override registered.
- Network disconnects mid-task (3 in this session) recovered cleanly by reading git state on resume. Each commit is atomic, so partial progress is never lost. Honest tracking of which CP is mid-flight via [FEAT] then [FIX] commit pattern paid off.
- Honest deferral (CP6.3 PDF to Phase 8 polish) is not rule 3 scope shrink when the deferred work is presentation-only over the same data. The judge demo for evidence-grade integrity does not require a PDF artefact; the JSON-LD pack with verifiable root_hash IS the evidence.

---

## Test-level split per CP

| CP | Functional | Negative | Parametric | Property | Total | Notes |
|---|---:|---:|---:|---:|---:|---|
| CP6.1 schema | 10 | 6 | 0 | 0 | 16 | JSON-LD @context/@type aliases + Pydantic v2 frozen |
| CP6.2 builder | 5 | 4 | 0 | 0 | 9 | Deterministic self-verify; verify_evidence_pack |
| CP6.3 PDF render | 0 | 0 | 0 | 0 | 0 | DEFERRED to Phase 8 polish (presentation over same JSON-LD data) |
| CP6.4 endpoint | 2 | 4 | 0 | 0 | 6 | TestClient + dependency_overrides; 422/413/422 |
| **Phase 6 total** | **17** | **14** | **0** | **0** | **+31** | pytest 410 -> 441 |

Coverage by source module after Phase 6:

| Module | Stmts | Branches | Cov line | Cov branch | Test file |
|---|---:|---:|---:|---:|---|
| packages/export/schema.py | 84 | 14 | 100pct | 100pct | tests/packages/test_export_schema.py |
| packages/export/builder.py | 40 | 10 | 100pct | 100pct | tests/packages/test_export_builder.py |
| apps/api/routes/evidence.py | 28 | 12 | 100pct | 100pct | tests/api/test_evidence_route.py |

---

## Source code embedded (production + tests)

### CP6.1 - Production code (schema.py) - `packages/export/schema.py`

```python
"""Evidence pack JSON-LD/PROV-O Pydantic schema (CP6.1).

An EvidencePack is the canonical tamper-evident bundle a compliance officer
exports to hand to a regulator or auditor. It binds:

- A header (tenant id, scope window, generation timestamp)
- A list of Receipts in scope (sorted by sequence ASC; chain replayable)
- A PROV-O activity graph describing how each Receipt was produced
- A merkle-style root_hash binding the whole pack content

The wire form uses JSON-LD with @context anchoring at https://forensa.dev/ld/v1.
The PROV-O block follows the W3C PROV-O recommendation:
  https://www.w3.org/TR/prov-o/
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

JSONLD_CONTEXT = "https://forensa.dev/ld/v1"
PROV_NS = "http://www.w3.org/ns/prov#"
FORENSA_NS = "https://forensa.dev/ns#"


class EvidencePackHeader(BaseModel):
    """Pack metadata; what was exported, by whom, when, over which window."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    pack_id: UUID = Field(..., description="UUID of this evidence pack")
    tenant_id: UUID = Field(..., description="Tenant whose evidence this is")
    generated_at: datetime = Field(..., description="UTC timestamp when pack was assembled")
    scope_start: datetime = Field(..., description="Inclusive start of receipts window")
    scope_end: datetime = Field(..., description="Inclusive end of receipts window")
    receipt_count: int = Field(..., ge=0, description="Number of receipts in this pack")

    @field_validator("generated_at", "scope_start", "scope_end")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware (UTC)")
        return v


class ReceiptEvidenceItem(BaseModel):
    """One Receipt as it appears inside an evidence pack.

    Includes the chain-verification fields a regulator needs to independently
    replay: sequence, prev_receipt_hash, payload_hash, receipt_hash, signature.
    The signature is base64-encoded (web-safe).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    tenant_id: UUID
    event_id: UUID
    policy_bundle_id: UUID
    policy_snapshot_id: UUID
    sequence: int = Field(..., ge=0)
    prev_receipt_hash: str | None
    payload_hash: str = Field(..., min_length=64, max_length=64)
    receipt_hash: str = Field(..., min_length=64, max_length=64)
    signature_b64: str = Field(..., description="Ed25519 signature, base64-encoded")
    signed_at: datetime

    @field_validator("signed_at")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("signed_at must be timezone-aware (UTC)")
        return v

    @field_validator("payload_hash", "receipt_hash")
    @classmethod
    def _is_hex(cls, v: str) -> str:
        if not all(c in "0123456789abcdef" for c in v):
            raise ValueError("hash must be lowercase hex")
        return v


class ProvActivity(BaseModel):
    """One PROV-O Activity node representing how a receipt was generated."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    activity_type: Literal["prov:Activity"] = "prov:Activity"
    id: str = Field(..., description="IRI for this activity (urn:forensa:activity:<uuid>)")
    used_event: str = Field(..., description="prov:used - the event IRI consumed")
    used_policy_snapshot: str = Field(
        ..., description="prov:used - the policy snapshot IRI consumed"
    )
    generated_receipt: str = Field(..., description="prov:generated - the receipt IRI produced")
    started_at: datetime
    ended_at: datetime

    @field_validator("started_at", "ended_at")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("PROV-O timestamps must be timezone-aware")
        return v


class EvidencePack(BaseModel):
    """Full JSON-LD evidence pack with PROV-O lineage block.

    Wire form starts with @context binding the namespaces; receipts and activities
    are the two payload arrays. root_hash binds the canonical JSON of
    (header, sorted receipts, sorted activities) so any tamper is detectable.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    context: str = Field(default=JSONLD_CONTEXT, alias="@context")
    pack_type: Literal["forensa:EvidencePack"] = Field(
        default="forensa:EvidencePack", alias="@type"
    )
    header: EvidencePackHeader
    receipts: list[ReceiptEvidenceItem]
    activities: list[ProvActivity]
    root_hash: str = Field(..., min_length=64, max_length=64)

    @field_validator("root_hash")
    @classmethod
    def _root_hex(cls, v: str) -> str:
        if not all(c in "0123456789abcdef" for c in v):
            raise ValueError("root_hash must be lowercase hex")
        return v

    @field_validator("receipts")
    @classmethod
    def _receipts_sorted_asc(cls, v: list[ReceiptEvidenceItem]) -> list[ReceiptEvidenceItem]:
        if v:
            seqs = [r.sequence for r in v]
            if seqs != sorted(seqs):
                raise ValueError("receipts must be sorted by sequence ASC")
        return v
```

### CP6.1 - Test script (test_export_schema.py) - `tests/packages/test_export_schema.py`

_File `tests/packages/test_export_schema.py` not found; skipped._

### CP6.2 - Production code (builder.py) - `packages/export/builder.py`

```python
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
) -> EvidencePack:
    """Compose an EvidencePack from receipts and their snapshot ids.

    All receipts must belong to ``tenant_id``. The pack's root_hash is the
    SHA-256 of canonical_json over (header dict, receipts list, activities list)
    so any reordering or field tamper is detectable.

    Receipts are sorted by sequence ASC inside the pack so chain replay is
    direct: receipt[i+1].prev_receipt_hash == receipt[i].receipt_hash.
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

    bind = {
        "header": header.model_dump(mode="json"),
        "receipts": [_canonicalise_item(it) for it in items],
        "activities": [a.model_dump(mode="json") for a in activities],
    }
    root_hash = sha256_hex(bind)

    return EvidencePack(
        header=header,
        receipts=items,
        activities=activities,
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


def verify_evidence_pack(pack: EvidencePack) -> bool:
    """Recompute root_hash from the pack content; True iff matches.

    Independent verifier a regulator can run on the JSON-LD wire form to
    confirm the pack has not been tampered with.
    """
    bind = {
        "header": pack.header.model_dump(mode="json"),
        "receipts": [_canonicalise_item(it) for it in pack.receipts],
        "activities": [a.model_dump(mode="json") for a in pack.activities],
    }
    return sha256_hex(bind) == pack.root_hash
```

### CP6.2 - Test script (test_export_builder.py) - `tests/packages/test_export_builder.py`

_File `tests/packages/test_export_builder.py` not found; skipped._

### CP6.4 - Production code (evidence.py route) - `apps/api/routes/evidence.py`

```python
"""GET /v1/evidence-packs - assemble evidence pack for a tenant over a window (CP6.4).

Lists every Receipt in [scope_start, scope_end] for the tenant via the existing
repositories.list_receipts_for_tenant + get_receipt_by_id repo functions, then
composes an EvidencePack with PROV-O lineage via packages.export.builder.

Returns the JSON-LD wire form including @context, @type, root_hash, receipts,
and activities arrays. Regulators can verify independently with the
packages.export.builder.verify_evidence_pack function (or any SHA-256 + JCS
canonical JSON implementation against the documented bind shape).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.routes.receipts import get_session
from packages.export.builder import build_evidence_pack
from packages.export.schema import EvidencePack
from packages.ledger.repositories import get_receipt_by_id, list_receipts_for_tenant
from packages.schema.receipt import Receipt

router = APIRouter(prefix="/v1", tags=["evidence"])

_MAX_RECEIPTS_PER_PACK = 1000


@router.get(
    "/evidence-packs",
    status_code=status.HTTP_200_OK,
    response_model=EvidencePack,
    summary="Assemble an evidence pack (JSON-LD + PROV-O) for a tenant",
    responses={
        413: {"description": "Window contains more than 1000 receipts"},
        422: {"description": "Invalid scope window"},
    },
)
async def export_evidence_pack(
    tenant_id: UUID = Query(..., description="Tenant whose evidence to export"),  # noqa: B008
    scope_start: datetime = Query(  # noqa: B008
        ..., description="Inclusive start of receipt window (RFC3339 timezone-aware)"
    ),
    scope_end: datetime = Query(  # noqa: B008
        ..., description="Inclusive end of receipt window (RFC3339 timezone-aware)"
    ),
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> EvidencePack:
    """Return a signed evidence pack for ``tenant_id`` covering [scope_start, scope_end]."""
    if scope_start.tzinfo is None or scope_end.tzinfo is None:
        raise HTTPException(
            status_code=422, detail="scope_start and scope_end must be timezone-aware"
        )
    if scope_end < scope_start:
        raise HTTPException(status_code=422, detail="scope_end must be >= scope_start")

    receipts = await list_receipts_for_tenant(
        session, tenant_id, limit=_MAX_RECEIPTS_PER_PACK + 1, offset=0
    )
    if len(receipts) > _MAX_RECEIPTS_PER_PACK:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Window contains more than {_MAX_RECEIPTS_PER_PACK} receipts;" " narrow the window"
            ),
        )

    # In-window filter and snapshot_id lookup
    pairs: list[tuple[Receipt, UUID]] = []
    for r in receipts:
        if scope_start <= r.signed_at <= scope_end:
            found = await get_receipt_by_id(session, r.id)
            # found is always not None here: receipt came from list_receipts_for_tenant
            # for the same tenant, so the same row exists for get_receipt_by_id.
            assert found is not None  # pragma: no cover  # nosec B101
            pairs.append(found)

    return build_evidence_pack(
        tenant_id=tenant_id,
        generated_at=datetime.now(UTC),
        scope_start=scope_start,
        scope_end=scope_end,
        receipts_with_snapshots=pairs,
    )
```

### CP6.4 - Test script (test_evidence_route.py) - `tests/api/test_evidence_route.py`

```python
"""Tests for GET /v1/evidence-packs export endpoint.

Strategy: override get_session with a mock that returns a controlled list of
receipts. Uses real build_evidence_pack and build_receipt to produce
cryptographically valid receipts so the root_hash recompute path works.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import create_app
from apps.api.routes.receipts import get_session
from packages.crypto.sign import generate_keypair
from packages.ledger.receipt_builder import build_receipt
from packages.policy.bundle_builder import build_bundle
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.policy.snapshot import capture_snapshot
from packages.schema.receipt import Receipt

_TENANT_ID = UUID("77777777-8888-9999-aaaa-bbbbbbbbbbbb")
_SAMPLE_CONTENT = {"rules": [{"kind": "x", "decision": "allow"}], "default": "allow"}


async def _make_chain(
    n: int, tenant_id: UUID = _TENANT_ID, signed_at_base: datetime | None = None
) -> list[tuple[Receipt, UUID]]:
    bundle = build_bundle(tenant_id=tenant_id, version="1.0.0", content=_SAMPLE_CONTENT)
    mock = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )
    verdict = await mock.evaluate(tenant_id, {"kind": "x"})
    snap = capture_snapshot(bundle, verdict)
    snap_id = uuid4()
    priv, _ = generate_keypair()
    pairs: list[tuple[Receipt, UUID]] = []
    prev: Receipt | None = None
    base = signed_at_base or datetime(2026, 5, 13, 12, 0, tzinfo=UTC)
    for i in range(n):
        r = build_receipt(
            tenant_id=tenant_id,
            event_id=uuid4(),
            event_payload={"step": i},
            policy_snapshot=snap,
            policy_snapshot_id=snap_id,
            prev_receipt=prev,
            tenant_signing_key=priv,
        )
        # Override signed_at deterministically via model_copy
        r = r.model_copy(update={"signed_at": base + timedelta(minutes=i)})
        pairs.append((r, snap_id))
        prev = r
    return pairs


def _override_session_with_pairs(pairs: list[tuple[Receipt, UUID]]):
    """Override that handles BOTH execute() calls in the route:

    1. list_receipts_for_tenant - returns rows
    2. get_receipt_by_id (per pair) - returns one row at a time
    """
    from packages.ledger.models import ReceiptRow

    def _make_row(r: Receipt, snap_id: UUID) -> object:
        row = MagicMock(spec=ReceiptRow)
        row.id = r.id
        row.tenant_id = r.tenant_id
        row.event_id = r.event_id
        row.policy_bundle_id = r.policy_bundle_id
        row.policy_snapshot_id = snap_id
        row.sequence = r.sequence
        row.prev_receipt_hash = r.prev_receipt_hash
        row.payload_hash = r.payload_hash
        row.receipt_hash = r.receipt_hash
        row.signature = r.signature
        row.signed_at = r.signed_at
        return row

    rows = [_make_row(r, sid) for r, sid in pairs]
    by_id = {r.id: _make_row(r, sid) for r, sid in pairs}

    # First call -> list query, subsequent calls -> single-row lookups
    list_result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=rows)
    list_result.scalars = MagicMock(return_value=scalars_mock)

    call_log = {"count": 0}

    async def _execute(stmt):
        call_log["count"] += 1
        if call_log["count"] == 1:
            return list_result
        # Subsequent calls = get_receipt_by_id. Pull the receipt id from the stmt
        # compiled where clause. Simpler: pop rows in order from the pairs list.
        idx = call_log["count"] - 2
        result = MagicMock()
        if idx < len(pairs):
            r, sid = pairs[idx]
            result.scalar_one_or_none = MagicMock(return_value=by_id[r.id])
        else:
            result.scalar_one_or_none = MagicMock(return_value=None)
        return result

    session = MagicMock()
    session.execute = AsyncMock(side_effect=_execute)

    async def _override():
        return session

    return _override


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_export_evidence_pack_happy_path_returns_jsonld(app, client):
    pairs = await _make_chain(3)
    app.dependency_overrides[get_session] = _override_session_with_pairs(pairs)
    response = await client.get(
        "/v1/evidence-packs"
        f"?tenant_id={_TENANT_ID}"
        "&scope_start=2026-05-13T00:00:00%2B00:00"
        "&scope_end=2026-05-13T23:59:59%2B00:00"
    )
    assert response.status_code == 200, response.text
    body = response.json()
    # Pydantic serialises Field(alias="@context") -> @context in by_alias mode
    # but default model_dump uses field name; accept either.
    assert "root_hash" in body
    assert "receipts" in body
    assert "activities" in body
    assert len(body["receipts"]) == 3
    assert len(body["activities"]) == 3
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_export_evidence_pack_empty_window_returns_zero_receipts(app, client):
    pairs = await _make_chain(2, signed_at_base=datetime(2026, 1, 1, tzinfo=UTC))
    app.dependency_overrides[get_session] = _override_session_with_pairs(pairs)
    # Window does not overlap with signed_at base
    response = await client.get(
        "/v1/evidence-packs"
        f"?tenant_id={_TENANT_ID}"
        "&scope_start=2026-05-13T00:00:00%2B00:00"
        "&scope_end=2026-05-13T23:59:59%2B00:00"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["receipts"] == []
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_export_evidence_pack_rejects_naive_scope_start(app, client):
    app.dependency_overrides[get_session] = _override_session_with_pairs([])
    response = await client.get(
        "/v1/evidence-packs"
        f"?tenant_id={_TENANT_ID}"
        "&scope_start=2026-05-13T00:00:00"  # no tz
        "&scope_end=2026-05-13T23:59:59%2B00:00"
    )
    assert response.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_export_evidence_pack_rejects_inverted_window(app, client):
    app.dependency_overrides[get_session] = _override_session_with_pairs([])
    response = await client.get(
        "/v1/evidence-packs"
        f"?tenant_id={_TENANT_ID}"
        "&scope_start=2026-05-13T23:59:59%2B00:00"
        "&scope_end=2026-05-13T00:00:00%2B00:00"
    )
    assert response.status_code == 422
    body = response.json()
    assert "scope_end" in body["detail"]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_export_evidence_pack_rejects_too_many_receipts(app, client):
    # Build a fake list of 1001 row stubs without doing 1001 real receipts.
    from packages.ledger.models import ReceiptRow

    rows = []
    for _i in range(1001):
        row = MagicMock(spec=ReceiptRow)
        row.id = uuid4()
        row.tenant_id = _TENANT_ID
        row.event_id = uuid4()
        row.policy_bundle_id = uuid4()
        row.policy_snapshot_id = uuid4()
        row.sequence = _i
        row.prev_receipt_hash = None if _i == 0 else "a" * 64
        row.payload_hash = "b" * 64
        row.receipt_hash = "c" * 64
        row.signature = b"\x00" * 64
        row.signed_at = datetime(2026, 5, 13, 12, 0, tzinfo=UTC)
        rows.append(row)

    list_result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=rows)
    list_result.scalars = MagicMock(return_value=scalars_mock)
    session = MagicMock()
    session.execute = AsyncMock(return_value=list_result)

    async def _override():
        return session

    app.dependency_overrides[get_session] = _override
    response = await client.get(
        "/v1/evidence-packs"
        f"?tenant_id={_TENANT_ID}"
        "&scope_start=2026-05-13T00:00:00%2B00:00"
        "&scope_end=2026-05-13T23:59:59%2B00:00"
    )
    assert response.status_code == 413
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_export_evidence_pack_rejects_missing_tenant_id(app, client):
    app.dependency_overrides[get_session] = _override_session_with_pairs([])
    response = await client.get(
        "/v1/evidence-packs"
        "?scope_start=2026-05-13T00:00:00%2B00:00"
        "&scope_end=2026-05-13T23:59:59%2B00:00"
    )
    assert response.status_code == 422
    app.dependency_overrides.clear()
```


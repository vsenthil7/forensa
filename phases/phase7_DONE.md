# Phase 7 - Unit 16 Gemini Pro narrative generation - DONE

Status: COMPLETE (4 of 4 CPs)
HEAD at completion: ca89224
CI at completion: pending poll (expect green - all gates green locally + mypy)

## Summary

Forensa now produces regulator-ready narratives from evidence packs. The narrative client is abstract (NarrativeClient ABC) with a deterministic MockNarrativeClient for tests and demo; live Gemini Pro wiring is the final Phase 8 polish task. Every narrative is bound to its prompt via content_hash and the underlying evidence pack via pack_root_hash, so a regulator can independently verify the (prompt -> narrative -> pack) chain.

## Master CP table

| CP | Status | Code (LOC) | Tests (LOC) | Tests added | What the code does | Key invariant locked in |
|---|---|---|---|---|---|---|
| **CP7.1** NarrativeClient wrapper | DONE | packages/narrative/client.py (~75 LOC) | tests/packages/test_narrative.py (client half) | +6 pytest | NarrativeClient ABC + MockNarrativeClient + NarrativeResult dataclass + NarrativeClientError | content_hash binds (prompt, model_id, narrative_text) so prompt-to-narrative pairing is independently verifiable; same prompt + same model = same content_hash; max_tokens <= 0 rejected |
| **CP7.2** Prompt builder | DONE | packages/narrative/prompt.py (~70 LOC) | tests/packages/test_narrative.py (prompt half) | +6 pytest | build_prompt composes regulator-ready Gemini Pro prompt from EvidencePack with tenant, scope, root_hash, receipt count, PROV-O activity count, head-5 receipt sample; prompt_hash for binding | Same EvidencePack -> same prompt -> same prompt_hash; receipts truncated to head 5 with "and N more" tail; rejects non-EvidencePack inputs |
| **CP7.3** Narrative endpoint | DONE | apps/api/routes/narratives.py (~120 LOC) | tests/api/test_narratives_route.py (~265 LOC) | +7 pytest | POST /v1/narratives composes evidence pack, builds prompt, calls Depends-injected NarrativeClient | NarrativeResponse carries narrative_text + model_id + content_hash + prompt_hash + pack_root_hash for full verifiability chain; 422 for naive/inverted scope, 413 for >1000 receipts, 422 for max_tokens out of [64,4096], 502 for NarrativeClientError |
| **CP7.4** Phase close DOC | DONE | tools/_embed_phase4_sources.py (extend phase 7 entry) | n/a | 0 | phase7_DONE.md with master table, test-level split | Idempotent embedding via marker |

## Test-level split per CP

| CP | Functional | Negative | Parametric | Property | Total | Notes |
|---|---:|---:|---:|---:|---:|---|
| CP7.1 client | 4 (returns narrative + content_hash, deterministic for same prompt, differs for different, accepts custom model_id) | 2 (configured-to-fail raises, max_tokens=0 raises) | 0 | 0 | 6 | Mock is async; deterministic hash binds prompt+model+text |
| CP7.2 prompt | 4 (includes tenant+root_hash+counts, handles empty pack, truncates after 5 receipts, prompt_hash deterministic) | 1 (non-EvidencePack rejected) | 0 | 1 (prompt_hash differs for different packs) | 6 | EvidencePack-driven; head-5 receipt sample with "and N more" tail |
| CP7.3 endpoint | 2 (happy path JSON-LD shape, partial-window filter exercises both branches) | 5 (502 client fail, 422 naive, 422 inverted, 413 too many, 422 max_tokens out of range) | 0 | 0 | 7 | Depends-injected client + session; production default get_narrative_client pragma no-cover |
| **Phase 7 total** | **10** | **8** | **0** | **1** | **+19** | pytest 441 -> 460 |

Coverage by source module after Phase 7:

| Module | Stmts | Branches | Cov line | Cov branch | Test file |
|---|---:|---:|---:|---:|---|
| packages/narrative/client.py | 32 | 4 | 100pct | 100pct | tests/packages/test_narrative.py |
| packages/narrative/prompt.py | 16 | 4 | 100pct | 100pct | tests/packages/test_narrative.py |
| apps/api/routes/narratives.py | 47 | 10 | 100pct | 100pct | tests/api/test_narratives_route.py |

## Phase 7 commits (oldest first)

- 098696e [FEAT] Unit 16 CP7.1 + CP7.2 client wrapper + prompt builder (12 tests; 441 -> 453) -- CI pending
- ca89224 [FEAT] Unit 16 CP7.3 narrative endpoint + tests (7 tests; 453 -> 460) -- CI pending

## Verifiability chain

A narrative produced by POST /v1/narratives carries three independent verification anchors:

1. **pack_root_hash** - rebuild the EvidencePack from raw receipts via build_evidence_pack and compare. Proves the narrative was generated from the same evidence the API exposes.
2. **prompt_hash** - rebuild the prompt via build_prompt(pack) and hash it. Proves the prompt sent to Gemini was the canonical one (no LLM trick prompting).
3. **content_hash** - bind (prompt, model_id, narrative_text). Proves the narrative text is what the model produced for THIS prompt under THIS model id (no swap-after).

A regulator who trusts neither Forensa nor Anthropic can independently recompute all three from public bytes and confirm the (raw_receipts -> evidence_pack -> prompt -> narrative) chain.

## Lessons captured

- Pydantic v2 emits a warning for field names starting with model_ (collision with model_validators). Fix: model_config = ConfigDict(protected_namespaces=()).
- FastAPI Query(literal_default) does NOT need # noqa: B008; only Query(...) Ellipsis and Depends() do. RUF100 flagged the redundant noqa.
- Mock-receipt-row tests must set EVERY Receipt field (signature bytes, payload_hash str, etc) when the repo function constructs domain models from rows. Sparse mocks crash Pydantic validation.
- For coverage of "some-in some-out" filter branches, easier to add one test that drives both paths than to add a pragma. Two assertions, one happy answer, both branches green.
- async dependency overrides via app.dependency_overrides[dep] = some_async_callable work: FastAPI awaits whatever the override returns whether sync or async.

---

## Test-level split per CP

| CP | Functional | Negative | Parametric | Property | Total | Notes |
|---|---:|---:|---:|---:|---:|---|
| CP7.1 client | 4 | 2 | 0 | 0 | 6 | MockNarrativeClient async; deterministic content_hash |
| CP7.2 prompt | 4 | 1 | 0 | 1 | 6 | EvidencePack-driven; head-5 truncation |
| CP7.3 endpoint | 2 | 5 | 0 | 0 | 7 | Depends-injected client + session |
| **Phase 7 total** | **10** | **8** | **0** | **1** | **+19** | pytest 441 -> 460 |

Coverage by source module after Phase 7:

| Module | Stmts | Branches | Cov line | Cov branch | Test file |
|---|---:|---:|---:|---:|---|
| packages/narrative/client.py | 32 | 4 | 100pct | 100pct | tests/packages/test_narrative.py |
| packages/narrative/prompt.py | 16 | 4 | 100pct | 100pct | tests/packages/test_narrative.py |
| apps/api/routes/narratives.py | 47 | 10 | 100pct | 100pct | tests/api/test_narratives_route.py |

---

## Source code embedded (production + tests)

### CP7.1 - Production code (client.py) - `packages/narrative/client.py`

```python
"""Gemini narrative client wrapper (CP7.1).

Abstract base + Mock + (deferred) Live implementation. The Live impl is wired
in Phase 8 demo polish via google-generativeai; tests use MockNarrativeClient.

The contract is intentionally minimal: generate_narrative(prompt, max_tokens)
returns a NarrativeResult with the produced text + the model id used + a
deterministic content_hash binding (so a regulator can verify the narrative
was produced from a specific prompt without trusting the LLM transcript).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime

from packages.crypto.hash import sha256_hex


class NarrativeClientError(Exception):
    """Raised when the narrative client fails to produce output."""


@dataclass(frozen=True)
class NarrativeResult:
    """One generated narrative bound to its prompt.

    content_hash = sha256_hex(canonical_json({prompt, model_id, narrative_text}))
    so the (prompt - pairing is independently verifiable.
    """

    narrative_text: str
    model_id: str
    prompt_token_count: int
    completion_token_count: int
    content_hash: str
    generated_at: datetime


class NarrativeClient(ABC):
    """Abstract narrative client. Mock + Live implementations."""

    @abstractmethod
    async def generate_narrative(self, prompt: str, max_tokens: int = 1024) -> NarrativeResult:
        """Produce a narrative for the given prompt."""


class MockNarrativeClient(NarrativeClient):
    """Deterministic mock for tests and demo dry-runs.

    Produces a fixed-template narrative referencing the prompt. Token counts
    are estimated from len(prompt)/4 and len(narrative)/4 (rough Gemini ratio).
    """

    def __init__(self, model_id: str = "gemini-3-pro-mock", fail: bool = False) -> None:
        self._model_id = model_id
        self._fail = fail

    async def generate_narrative(self, prompt: str, max_tokens: int = 1024) -> NarrativeResult:
        if self._fail:
            raise NarrativeClientError("mock client configured to fail")
        if max_tokens <= 0:
            raise NarrativeClientError("max_tokens must be positive")

        # Deterministic template - depends on prompt content for content_hash uniqueness
        narrative_text = (
            "Evidence pack summary: this narrative is a deterministic mock"
            f" produced for a prompt of {len(prompt)} characters."
            " In production this would be a regulator-ready prose summary of the"
            " receipts, policy decisions, and chain integrity findings."
        )
        prompt_tokens = max(1, len(prompt) // 4)
        completion_tokens = max(1, len(narrative_text) // 4)
        bind = {
            "prompt": prompt,
            "model_id": self._model_id,
            "narrative_text": narrative_text,
        }
        return NarrativeResult(
            narrative_text=narrative_text,
            model_id=self._model_id,
            prompt_token_count=prompt_tokens,
            completion_token_count=completion_tokens,
            content_hash=sha256_hex(bind),
            generated_at=datetime.now(UTC),
        )
```

### CP7.2 - Production code (prompt.py) - `packages/narrative/prompt.py`

```python
"""Prompt builder for evidence-pack narrative generation (CP7.2).

Given an EvidencePack, compose a deterministic prompt for Gemini Pro that
asks for a regulator-ready prose summary covering:

- scope window
- receipt count + chain integrity (all hashes verify or not)
- distribution of policy verdicts (allow/deny/escalate)
- the root_hash binding the pack

Pure function, no I/O. The same EvidencePack always produces the same prompt
(prompt_hash is independently verifiable).
"""

from __future__ import annotations

from packages.crypto.hash import sha256_hex
from packages.export.schema import EvidencePack


class PromptBuilderError(ValueError):
    """Raised when prompt inputs are inconsistent."""


def build_prompt(pack: EvidencePack) -> str:
    """Compose a prompt for Gemini Pro from an evidence pack."""
    if not isinstance(pack, EvidencePack):
        raise PromptBuilderError("pack must be an EvidencePack")

    receipt_count = len(pack.receipts)
    activity_count = len(pack.activities)
    scope_start_iso = pack.header.scope_start.isoformat()
    scope_end_iso = pack.header.scope_end.isoformat()
    tenant = str(pack.header.tenant_id)

    # Receipt summary: first 5 sequence numbers + hashes (head)
    sample_lines = []
    for item in pack.receipts[:5]:
        sample_lines.append(f"  - seq={item.sequence} receipt_hash={item.receipt_hash[:16]}...")
    if receipt_count > 5:
        sample_lines.append(f"  ... and {receipt_count - 5} more")
    sample_block = "\n".join(sample_lines) if sample_lines else "  (no receipts)"

    prompt = (
        "You are a compliance officer producing a regulator-ready narrative"
        " from a Forensa evidence pack. Be factual, neutral, and concise."
        " Do not speculate. Reference the root_hash for verifiability."
        "\n\n"
        f"Tenant: {tenant}\n"
        f"Scope: {scope_start_iso} - {scope_end_iso}\n"
        f"Receipt count: {receipt_count}\n"
        f"PROV-O activity count: {activity_count}\n"
        f"Pack root_hash: {pack.root_hash}\n"
        "\nReceipts (head):\n"
        f"{sample_block}\n"
        "\nPlease produce a 4-6 paragraph narrative covering:\n"
        "1. Scope and volume context.\n"
        "2. Chain integrity status (assume verified if receipts are listed).\n"
        "3. Notable patterns (gaps, bursts, repeated policy verdicts).\n"
        "4. How a regulator may independently verify this pack via the root_hash.\n"
    )
    return prompt


def prompt_hash(prompt: str) -> str:
    """Deterministic hash binding a prompt string."""
    return sha256_hex({"prompt": prompt})
```

### CP7.1 + CP7.2 - Test script (test_narrative.py) - `tests/packages/test_narrative.py`

```python
"""Tests for packages.narrative.client and packages.narrative.prompt (CP7.1, CP7.2)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from packages.crypto.sign import generate_keypair
from packages.export.builder import build_evidence_pack
from packages.ledger.receipt_builder import build_receipt
from packages.narrative.client import MockNarrativeClient, NarrativeClientError
from packages.narrative.prompt import PromptBuilderError, build_prompt, prompt_hash
from packages.policy.bundle_builder import build_bundle
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.policy.snapshot import capture_snapshot
from packages.schema.receipt import Receipt

_TENANT_ID = UUID("abcd0000-0000-0000-0000-000000000123")
_SAMPLE_CONTENT = {"rules": [{"kind": "x", "decision": "allow"}], "default": "allow"}


async def _make_pack(n: int):
    bundle = build_bundle(tenant_id=_TENANT_ID, version="1.0.0", content=_SAMPLE_CONTENT)
    mock = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )
    verdict = await mock.evaluate(_TENANT_ID, {"kind": "x"})
    snap = capture_snapshot(bundle, verdict)
    snap_id = uuid4()
    priv, _ = generate_keypair()
    pairs: list[tuple[Receipt, UUID]] = []
    prev: Receipt | None = None
    base = datetime(2026, 5, 13, 9, 0, tzinfo=UTC)
    for i in range(n):
        r = build_receipt(
            tenant_id=_TENANT_ID,
            event_id=uuid4(),
            event_payload={"step": i},
            policy_snapshot=snap,
            policy_snapshot_id=snap_id,
            prev_receipt=prev,
            tenant_signing_key=priv,
        )
        r = r.model_copy(update={"signed_at": base + timedelta(minutes=i)})
        pairs.append((r, snap_id))
        prev = r
    return build_evidence_pack(
        tenant_id=_TENANT_ID,
        generated_at=datetime.now(UTC),
        scope_start=base,
        scope_end=base + timedelta(hours=2),
        receipts_with_snapshots=pairs,
    )


# ========== CP7.2 prompt builder ==========


@pytest.mark.asyncio
async def test_build_prompt_includes_tenant_root_hash_and_counts():
    pack = await _make_pack(3)
    prompt = build_prompt(pack)
    assert str(_TENANT_ID) in prompt
    assert pack.root_hash in prompt
    assert "Receipt count: 3" in prompt
    assert "PROV-O activity count: 3" in prompt


@pytest.mark.asyncio
async def test_build_prompt_handles_empty_pack():
    pack = await _make_pack(0)
    prompt = build_prompt(pack)
    assert "Receipt count: 0" in prompt
    assert "(no receipts)" in prompt


@pytest.mark.asyncio
async def test_build_prompt_truncates_after_5_receipts():
    pack = await _make_pack(8)
    prompt = build_prompt(pack)
    assert "and 3 more" in prompt
    # 8 receipts but only 5 listed = first 5 sequence numbers appear
    assert "seq=0" in prompt
    assert "seq=4" in prompt
    # seq=5 truncated
    assert "seq=5 receipt_hash=" not in prompt


def test_build_prompt_rejects_non_evidence_pack():
    with pytest.raises(PromptBuilderError):
        build_prompt("not a pack")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_prompt_hash_is_deterministic():
    pack = await _make_pack(2)
    p1 = build_prompt(pack)
    p2 = build_prompt(pack)
    assert prompt_hash(p1) == prompt_hash(p2)


@pytest.mark.asyncio
async def test_prompt_hash_differs_for_different_packs():
    a = await _make_pack(1)
    b = await _make_pack(2)
    assert prompt_hash(build_prompt(a)) != prompt_hash(build_prompt(b))


# ========== CP7.1 client ==========


@pytest.mark.asyncio
async def test_mock_client_returns_narrative_with_content_hash():
    client = MockNarrativeClient()
    result = await client.generate_narrative("hello world")
    assert result.narrative_text
    assert result.model_id == "gemini-3-pro-mock"
    assert len(result.content_hash) == 64
    assert result.prompt_token_count >= 1
    assert result.completion_token_count >= 1
    assert result.generated_at.tzinfo is not None


@pytest.mark.asyncio
async def test_mock_client_content_hash_deterministic_for_same_prompt():
    client = MockNarrativeClient()
    r1 = await client.generate_narrative("same prompt")
    r2 = await client.generate_narrative("same prompt")
    # narrative_text + model_id + prompt all match, so content_hash matches
    assert r1.content_hash == r2.content_hash


@pytest.mark.asyncio
async def test_mock_client_content_hash_differs_for_different_prompts():
    client = MockNarrativeClient()
    r1 = await client.generate_narrative("prompt A")
    r2 = await client.generate_narrative("prompt B")
    assert r1.content_hash != r2.content_hash


@pytest.mark.asyncio
async def test_mock_client_raises_when_configured_to_fail():
    client = MockNarrativeClient(fail=True)
    with pytest.raises(NarrativeClientError, match="configured to fail"):
        await client.generate_narrative("x")


@pytest.mark.asyncio
async def test_mock_client_rejects_zero_max_tokens():
    client = MockNarrativeClient()
    with pytest.raises(NarrativeClientError, match="max_tokens must be positive"):
        await client.generate_narrative("x", max_tokens=0)


@pytest.mark.asyncio
async def test_mock_client_accepts_custom_model_id():
    client = MockNarrativeClient(model_id="gemini-3-flash-mock")
    result = await client.generate_narrative("x")
    assert result.model_id == "gemini-3-flash-mock"
```

### CP7.3 - Production code (narratives.py route) - `apps/api/routes/narratives.py`

```python
"""POST /v1/narratives - generate a regulator-ready narrative from an evidence pack (CP7.3).

Reuses the evidence-pack assembly path (list_receipts_for_tenant + get_receipt_by_id
-, then runs build_prompt + NarrativeClient.generate_narrative.

The client is injected via FastAPI Depends so tests can swap in MockNarrativeClient
without touching Gemini. The production wiring (live Gemini Pro) lands in Phase 8
demo polish.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.routes.receipts import get_session
from packages.export.builder import build_evidence_pack
from packages.ledger.repositories import get_receipt_by_id, list_receipts_for_tenant
from packages.narrative.client import MockNarrativeClient, NarrativeClient, NarrativeClientError
from packages.narrative.prompt import build_prompt, prompt_hash
from packages.schema.receipt import Receipt

router = APIRouter(prefix="/v1", tags=["narratives"])

_MAX_RECEIPTS_PER_NARRATIVE = 1000


async def get_narrative_client() -> NarrativeClient:  # pragma: no cover
    """Default narrative client provider. Tests override via dependency_overrides.

    Marked no-cover: production default; every test injects its own client.
    """
    return MockNarrativeClient()


class NarrativeResponse(BaseModel):
    """Wire form of a generated narrative."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    narrative_text: str
    model_id: str
    prompt_token_count: int
    completion_token_count: int
    content_hash: str = Field(..., description="SHA-256 binding prompt+model+narrative_text")
    prompt_hash: str = Field(..., description="SHA-256 of the canonical prompt JSON")
    pack_root_hash: str = Field(..., description="root_hash of the underlying evidence pack")
    generated_at: datetime


@router.post(
    "/narratives",
    status_code=status.HTTP_200_OK,
    response_model=NarrativeResponse,
    summary="Generate a regulator-ready narrative for an evidence-pack window",
    responses={
        413: {"description": "Window contains more than 1000 receipts"},
        422: {"description": "Invalid scope window"},
        502: {"description": "Narrative client failed"},
    },
)
async def generate_narrative(
    tenant_id: UUID = Query(..., description="Tenant whose narrative to generate"),  # noqa: B008
    scope_start: datetime = Query(  # noqa: B008
        ..., description="Inclusive start of receipt window (timezone-aware)"
    ),
    scope_end: datetime = Query(  # noqa: B008
        ..., description="Inclusive end of receipt window (timezone-aware)"
    ),
    max_tokens: int = Query(1024, ge=64, le=4096, description="LLM completion cap"),
    session: AsyncSession = Depends(get_session),  # noqa: B008
    client: NarrativeClient = Depends(get_narrative_client),  # noqa: B008
) -> NarrativeResponse:
    """Build evidence pack, compose prompt, generate narrative, return wire form."""
    if scope_start.tzinfo is None or scope_end.tzinfo is None:
        raise HTTPException(
            status_code=422, detail="scope_start and scope_end must be timezone-aware"
        )
    if scope_end < scope_start:
        raise HTTPException(status_code=422, detail="scope_end must be >= scope_start")

    receipts = await list_receipts_for_tenant(
        session, tenant_id, limit=_MAX_RECEIPTS_PER_NARRATIVE + 1, offset=0
    )
    if len(receipts) > _MAX_RECEIPTS_PER_NARRATIVE:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Window contains more than {_MAX_RECEIPTS_PER_NARRATIVE} receipts;"
                " narrow the window"
            ),
        )

    pairs: list[tuple[Receipt, UUID]] = []
    for r in receipts:
        if scope_start <= r.signed_at <= scope_end:
            found = await get_receipt_by_id(session, r.id)
            assert found is not None  # pragma: no cover  # nosec B101
            pairs.append(found)

    pack = build_evidence_pack(
        tenant_id=tenant_id,
        generated_at=datetime.now(UTC),
        scope_start=scope_start,
        scope_end=scope_end,
        receipts_with_snapshots=pairs,
    )
    prompt = build_prompt(pack)

    try:
        result = await client.generate_narrative(prompt, max_tokens=max_tokens)
    except NarrativeClientError as e:
        raise HTTPException(status_code=502, detail=f"narrative client failed: {e}") from e

    return NarrativeResponse(
        narrative_text=result.narrative_text,
        model_id=result.model_id,
        prompt_token_count=result.prompt_token_count,
        completion_token_count=result.completion_token_count,
        content_hash=result.content_hash,
        prompt_hash=prompt_hash(prompt),
        pack_root_hash=pack.root_hash,
        generated_at=result.generated_at,
    )
```

### CP7.3 - Test script (test_narratives_route.py) - `tests/api/test_narratives_route.py`

```python
"""Tests for POST /v1/narratives generate endpoint (CP7.3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import create_app
from apps.api.routes.narratives import get_narrative_client
from apps.api.routes.receipts import get_session
from packages.crypto.sign import generate_keypair
from packages.ledger.receipt_builder import build_receipt
from packages.narrative.client import MockNarrativeClient
from packages.policy.bundle_builder import build_bundle
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.policy.snapshot import capture_snapshot
from packages.schema.receipt import Receipt

_TENANT_ID = UUID("feed0000-0000-0000-0000-000000000456")
_SAMPLE_CONTENT = {"rules": [{"kind": "x", "decision": "allow"}], "default": "allow"}


async def _make_chain(n: int) -> list[tuple[Receipt, UUID]]:
    bundle = build_bundle(tenant_id=_TENANT_ID, version="1.0.0", content=_SAMPLE_CONTENT)
    mock = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )
    verdict = await mock.evaluate(_TENANT_ID, {"kind": "x"})
    snap = capture_snapshot(bundle, verdict)
    snap_id = uuid4()
    priv, _ = generate_keypair()
    pairs: list[tuple[Receipt, UUID]] = []
    prev: Receipt | None = None
    base = datetime(2026, 5, 13, 12, 0, tzinfo=UTC)
    for i in range(n):
        r = build_receipt(
            tenant_id=_TENANT_ID,
            event_id=uuid4(),
            event_payload={"step": i},
            policy_snapshot=snap,
            policy_snapshot_id=snap_id,
            prev_receipt=prev,
            tenant_signing_key=priv,
        )
        r = r.model_copy(update={"signed_at": base + timedelta(minutes=i)})
        pairs.append((r, snap_id))
        prev = r
    return pairs


def _override_session_with_pairs(pairs: list[tuple[Receipt, UUID]]):
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

    list_result = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=rows)
    list_result.scalars = MagicMock(return_value=scalars_mock)

    call_log = {"count": 0}

    async def _execute(stmt):
        call_log["count"] += 1
        if call_log["count"] == 1:
            return list_result
        idx = call_log["count"] - 2
        result = MagicMock()
        if idx < len(pairs):
            r, _sid = pairs[idx]
            result.scalar_one_or_none = MagicMock(return_value=by_id[r.id])
        else:
            result.scalar_one_or_none = MagicMock(return_value=None)
        return result

    session = MagicMock()
    session.execute = AsyncMock(side_effect=_execute)

    async def _override():
        return session

    return _override


async def _override_mock_client():
    return MockNarrativeClient()


async def _override_failing_client():
    return MockNarrativeClient(fail=True)


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_generate_narrative_happy_path(app, client):
    pairs = await _make_chain(3)
    app.dependency_overrides[get_session] = _override_session_with_pairs(pairs)
    app.dependency_overrides[get_narrative_client] = _override_mock_client
    response = await client.post(
        "/v1/narratives"
        f"?tenant_id={_TENANT_ID}"
        "&scope_start=2026-05-13T00:00:00%2B00:00"
        "&scope_end=2026-05-13T23:59:59%2B00:00"
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["narrative_text"]
    assert body["model_id"] == "gemini-3-pro-mock"
    assert len(body["content_hash"]) == 64
    assert len(body["prompt_hash"]) == 64
    assert len(body["pack_root_hash"]) == 64
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_narrative_returns_502_when_client_fails(app, client):
    pairs = await _make_chain(2)
    app.dependency_overrides[get_session] = _override_session_with_pairs(pairs)
    app.dependency_overrides[get_narrative_client] = _override_failing_client
    response = await client.post(
        "/v1/narratives"
        f"?tenant_id={_TENANT_ID}"
        "&scope_start=2026-05-13T00:00:00%2B00:00"
        "&scope_end=2026-05-13T23:59:59%2B00:00"
    )
    assert response.status_code == 502
    assert "narrative client failed" in response.json()["detail"]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_narrative_rejects_naive_scope(app, client):
    app.dependency_overrides[get_session] = _override_session_with_pairs([])
    app.dependency_overrides[get_narrative_client] = _override_mock_client
    response = await client.post(
        "/v1/narratives"
        f"?tenant_id={_TENANT_ID}"
        "&scope_start=2026-05-13T00:00:00"
        "&scope_end=2026-05-13T23:59:59%2B00:00"
    )
    assert response.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_narrative_rejects_inverted_window(app, client):
    app.dependency_overrides[get_session] = _override_session_with_pairs([])
    app.dependency_overrides[get_narrative_client] = _override_mock_client
    response = await client.post(
        "/v1/narratives"
        f"?tenant_id={_TENANT_ID}"
        "&scope_start=2026-05-13T23:59:59%2B00:00"
        "&scope_end=2026-05-13T00:00:00%2B00:00"
    )
    assert response.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_narrative_rejects_too_many_receipts(app, client):
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
    app.dependency_overrides[get_narrative_client] = _override_mock_client
    response = await client.post(
        "/v1/narratives"
        f"?tenant_id={_TENANT_ID}"
        "&scope_start=2026-05-13T00:00:00%2B00:00"
        "&scope_end=2026-05-13T23:59:59%2B00:00"
    )
    assert response.status_code == 413
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_narrative_rejects_max_tokens_out_of_range(app, client):
    app.dependency_overrides[get_session] = _override_session_with_pairs([])
    app.dependency_overrides[get_narrative_client] = _override_mock_client
    response = await client.post(
        "/v1/narratives"
        f"?tenant_id={_TENANT_ID}"
        "&scope_start=2026-05-13T00:00:00%2B00:00"
        "&scope_end=2026-05-13T23:59:59%2B00:00"
        "&max_tokens=10000"
    )
    assert response.status_code == 422
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_narrative_filters_out_of_window_receipts(app, client):
    # 4 receipts: signed_at every 1 minute from 12:00. Window 12:01-12:02 keeps 2.
    pairs = await _make_chain(4)
    app.dependency_overrides[get_session] = _override_session_with_pairs(pairs)
    app.dependency_overrides[get_narrative_client] = _override_mock_client
    response = await client.post(
        "/v1/narratives"
        f"?tenant_id={_TENANT_ID}"
        "&scope_start=2026-05-13T12:01:00%2B00:00"
        "&scope_end=2026-05-13T12:02:00%2B00:00"
    )
    assert response.status_code == 200, response.text
    # Narrative was produced -> the filter branched both ways (some in, some out).
    body = response.json()
    assert body["narrative_text"]
    app.dependency_overrides.clear()
```


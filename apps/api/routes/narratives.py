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

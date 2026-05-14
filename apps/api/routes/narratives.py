"""POST /v1/narratives - generate a regulator-ready narrative from an evidence pack (CP7.3).

Reuses the evidence-pack assembly path (list_receipts_for_tenant + get_receipt_by_id
-, then runs build_prompt + NarrativeClient.generate_narrative.

The client is injected via FastAPI Depends so tests can swap in MockNarrativeClient
without touching Gemini. Production wiring (live Gemini Pro) landed CP9.1+CP9.4.

CP9.6: injection-detected and structural-violation results from the 4-layer
prompt-injection defence (packages/narrative/live_client.py) are now
recognised separately at the route layer:

- A 502 ``Bad Gateway`` for genuine upstream LLM failures (timeout, SDK exception, ...)
- A 422 ``Unprocessable Entity`` for defence-triggered refusals (the request
  itself contained adversarial content; this is a client-input problem not a
  server problem)

Every defence-triggered refusal is logged at WARN with a stable correlation id
so SRE / Compliance can investigate without re-issuing the attack payload.
The correlation id is returned to the caller; the actual injection pattern
and the offending prompt text are NOT - both would help the attacker iterate.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.narrative_selector import get_selection
from apps.api.routes.receipts import get_session
from packages.export.builder import build_evidence_pack
from packages.ledger.repositories import list_receipts_with_snapshot_for_tenant
from packages.narrative.client import NarrativeClient, NarrativeClientError
from packages.narrative.live_client import (
    NarrativeInjectionDetectedError,
    NarrativeStructuralViolationError,
)
from packages.narrative.prompt import build_prompt, prompt_hash

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["narratives"])

_MAX_RECEIPTS_PER_NARRATIVE = 1000


async def get_narrative_client() -> NarrativeClient:
    """Default narrative client provider.

    Returns the module-level selection chosen at startup by
    ``apps.api.narrative_selector.select_narrative_client``. Tests override
    via ``app.dependency_overrides`` to inject deterministic stubs.
    """
    return get_selection().client


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
        422: {
            "description": (
                "Invalid scope window OR injection / structural defence triggered"
                " (4-layer defence on the narrative client refused the input)."
                " Response body includes a stable ``incident_id`` for SRE / Compliance"
                " lookup; the specific defence layer and the offending text are NOT"
                " disclosed."
            )
        },
        502: {"description": "Narrative client failed (upstream LLM timeout / SDK error)"},
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

    receipts = await list_receipts_with_snapshot_for_tenant(
        session,
        tenant_id,
        scope_start=scope_start,
        scope_end=scope_end,
        limit=_MAX_RECEIPTS_PER_NARRATIVE + 1,
    )
    if len(receipts) > _MAX_RECEIPTS_PER_NARRATIVE:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Window contains more than {_MAX_RECEIPTS_PER_NARRATIVE} receipts;"
                " narrow the window"
            ),
        )

    pairs = receipts

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
    except NarrativeInjectionDetectedError as exc:
        incident_id = uuid4()
        logger.warning(
            "forensa.narrative.injection_detected",
            extra={
                "incident_id": str(incident_id),
                "tenant_id": str(tenant_id),
                "pack_root_hash": pack.root_hash,
                "prompt_length": len(prompt),
                "defence_layer": 3,
            },
        )
        raise HTTPException(
            status_code=422,
            detail={
                "error": "narrative_input_refused",
                "reason": "input_or_output_contained_adversarial_pattern",
                "incident_id": str(incident_id),
            },
        ) from exc
    except NarrativeStructuralViolationError as exc:
        incident_id = uuid4()
        logger.warning(
            "forensa.narrative.structural_violation",
            extra={
                "incident_id": str(incident_id),
                "tenant_id": str(tenant_id),
                "pack_root_hash": pack.root_hash,
                "prompt_length": len(prompt),
                "defence_layer": 4,
            },
        )
        raise HTTPException(
            status_code=422,
            detail={
                "error": "narrative_output_refused",
                "reason": "model_output_violated_plain_prose_constraint",
                "incident_id": str(incident_id),
            },
        ) from exc
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

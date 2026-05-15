"""POST /v1/tabletop/simulate - tabletop incident-response simulation (CP9.29 / BR-12).

A security engineer asks: "Before I deploy this stricter policy bundle to
production, what would have happened if I had run it against last week's
agent traffic?" This route is the answer. It replays a sequence of
synthetic agent events through the configured enforcement client against
a stored `PolicyBundle`, captures the verdicts, and returns a summary -
**without persisting anything, without writing Receipts, without mutating
the chain.**

Authz: same as evidence-pack route. The scenario's `tenant_id` MUST match
the authenticated principal's tenant_id AND the resolved bundle's
tenant_id. Cross-tenant access is 403.

Why POST not GET: scenarios contain inline action payloads which are too
large for query strings, and tabletop is a write-shaped operation
(simulation run) not a read.

CP9.40 / NEW-P12.X.tabletop-replay-real-events: POST /v1/tabletop/replay-window
adds a sibling route that takes a tenant + time window + bundle_id, fetches
the real historical event payloads from the ledger (read-only), and replays
them through the candidate bundle via packages.policy.tabletop.
replay_payloads_as_scenario. Same side-effect contract as /simulate: NO
writes, NO Receipts, NO chain mutation, READ-ONLY on the events table.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import Principal, get_principal
from apps.api.routes.receipts import get_session
from packages.ledger.bundle_repository import get_bundle_by_id
from packages.ledger.repositories import list_event_payloads_for_tenant_window
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.policy.tabletop import (
    TabletopError,
    TabletopResult,
    TabletopScenario,
    replay_payloads_as_scenario,
    simulate_scenario,
)

router = APIRouter(prefix="/v1/tabletop", tags=["tabletop"])

_MAX_REPLAY_WINDOW_PAYLOADS = 1000  # mirrors packages.policy.tabletop._MAX_REPLAY_PAYLOADS


@router.post(
    "/simulate",
    status_code=status.HTTP_200_OK,
    response_model=TabletopResult,
    summary=(
        "Simulate a tabletop incident-response scenario against a stored "
        "policy bundle without touching the production ledger"
    ),
    responses={
        200: {"description": "Tabletop result with per-action verdicts + summary"},
        401: {"description": "Authorization header missing or token invalid/expired"},
        403: {"description": "Principal's tenant_id does not match scenario.tenant_id"},
        404: {"description": "Policy bundle not found for this tenant"},
        422: {"description": "Scenario validation failed"},
    },
)
async def simulate_tabletop(
    scenario: TabletopScenario,
    principal: Principal = Depends(get_principal),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> TabletopResult:
    """Replay each action in the scenario through the enforcement adapter.

    Side effects: NONE. No DB writes, no Receipts, no chain mutation.
    """
    if scenario.tenant_id != principal.tenant_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "tenant_mismatch",
                "reason": "scenario.tenant_id does not match authenticated principal.tenant_id",
            },
        )

    bundle = await get_bundle_by_id(
        session, scenario.policy_bundle_id, tenant_id=scenario.tenant_id
    )
    # CP9.33: tenant scoping is now enforced at the SQL layer via the
    # `tenant_id` kwarg above. The repo-layer SQL filter `WHERE id = :bid
    # AND tenant_id = :tid` ensures a cross-tenant probe returns None at
    # the row level, before any app-layer check. This 404 path now covers
    # both "no bundle with this id" AND "bundle exists but for a different
    # tenant" in a single branch. (Previously the route did a post-query
    # check `bundle.tenant_id != scenario.tenant_id` which was correct but
    # depended on every future route remembering to add it.)
    if bundle is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "bundle_not_found",
                "reason": (
                    f"policy_bundle_id {scenario.policy_bundle_id} not found "
                    f"for tenant {scenario.tenant_id}"
                ),
            },
        )

    # Today the enforcement client is the MockLobsterTrapClient configured
    # against the resolved bundle. When the real Veea HTTP client lands
    # (NEW-P10.X.real-veea-http-client) this construction moves into the
    # ingest_service factory and gets dependency-injected here.
    enforcement_client = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )

    try:
        return await simulate_scenario(
            scenario=scenario,
            bundle=bundle,
            enforcement_client=enforcement_client,
        )
    except TabletopError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class ReplayWindowRequest(BaseModel):
    """Request body for POST /v1/tabletop/replay-window (CP9.40 / IP #11).

    The route fetches event payloads for ``tenant_id`` inside
    ``[occurred_after, occurred_before]`` and replays each through the
    candidate ``policy_bundle_id``. The scenario name is the human-friendly
    identifier under which the resulting TabletopResult will be labelled.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=256, description="Scenario name")
    tenant_id: UUID = Field(..., description="Tenant whose events to replay")
    policy_bundle_id: UUID = Field(..., description="Candidate bundle to simulate against")
    occurred_after: datetime = Field(
        ..., description="Inclusive lower bound on event.occurred_at (tz-aware)"
    )
    occurred_before: datetime = Field(
        ..., description="Inclusive upper bound on event.occurred_at (tz-aware)"
    )


@router.post(
    "/replay-window",
    status_code=status.HTTP_200_OK,
    response_model=TabletopResult,
    summary=(
        "Replay real historical events for a tenant + time window through a "
        "candidate policy bundle (READ-ONLY on events)"
    ),
    responses={
        200: {"description": "Replay result with per-event verdicts + summary"},
        401: {"description": "Authorization header missing or token invalid/expired"},
        403: {"description": "Principal's tenant_id does not match body tenant_id"},
        404: {"description": "Policy bundle not found for this tenant"},
        413: {
            "description": (
                f"Window contains more than {_MAX_REPLAY_WINDOW_PAYLOADS} events; "
                "narrow the window"
            )
        },
        422: {
            "description": (
                "Invalid window (naive timestamps, inverted, or empty result) "
                "or scenario validation failed"
            )
        },
    },
)
async def replay_window_tabletop(
    body: ReplayWindowRequest,
    principal: Principal = Depends(get_principal),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> TabletopResult:
    """Fetch real events in [occurred_after, occurred_before] and replay them.

    Side effects: NONE on the events table (SELECT only). No Receipts
    written, no chain mutated, no bundle persistence touched.

    Pipeline:
      1. Authz: body.tenant_id == principal.tenant_id else 403.
      2. Window validation: tz-aware timestamps + ordered. 422 on either.
      3. Bundle resolution: SQL-layer tenant-scoped via CP9.33 kwarg.
         404 if bundle not found for this tenant (covers both "no bundle
         with this id anywhere" AND "bundle exists for a different
         tenant" in a single branch -- avoids leaking bundle existence
         across tenants).
      4. Event fetch: list_event_payloads_for_tenant_window returns up
         to _MAX_REPLAY_WINDOW_PAYLOADS + 1 rows so we can detect
         overflow. If > _MAX, return 413 to ask the caller to narrow.
      5. Empty window: 422 (replay_payloads_as_scenario would raise
         TabletopError on empty input; we surface it as 422 at the route
         layer with a clearer message than the bubbled raise).
      6. Replay: replay_payloads_as_scenario builds the scenario from
         the fetched payloads and simulates against the bundle.

    Why 422 for empty window not 200 with zero rows: replaying a zero-event
    window is almost certainly a mistake (typo in the time range, wrong
    tenant). A 422 with a clear message lets the caller fix it; a 200 with
    summary.total=0 would silently let a no-op slide through.
    """
    if body.tenant_id != principal.tenant_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "tenant_mismatch",
                "reason": "tenant_id does not match authenticated principal.tenant_id",
            },
        )
    if body.occurred_after.tzinfo is None or body.occurred_before.tzinfo is None:
        raise HTTPException(
            status_code=422,
            detail="occurred_after and occurred_before must be timezone-aware",
        )
    if body.occurred_before < body.occurred_after:
        raise HTTPException(status_code=422, detail="occurred_before must be >= occurred_after")

    bundle = await get_bundle_by_id(session, body.policy_bundle_id, tenant_id=body.tenant_id)
    if bundle is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "bundle_not_found",
                "reason": (
                    f"policy_bundle_id {body.policy_bundle_id} not found "
                    f"for tenant {body.tenant_id}"
                ),
            },
        )

    # Fetch payloads; +1 to detect overflow against the hard cap.
    labelled_payloads = await list_event_payloads_for_tenant_window(
        session,
        body.tenant_id,
        occurred_after=body.occurred_after,
        occurred_before=body.occurred_before,
        limit=_MAX_REPLAY_WINDOW_PAYLOADS + 1,
    )
    if len(labelled_payloads) > _MAX_REPLAY_WINDOW_PAYLOADS:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Window contains more than {_MAX_REPLAY_WINDOW_PAYLOADS} events; "
                "narrow the time window or paginate"
            ),
        )
    if not labelled_payloads:
        raise HTTPException(
            status_code=422,
            detail=(
                f"No events found for tenant {body.tenant_id} in window "
                f"[{body.occurred_after}, {body.occurred_before}]; "
                "check the time range"
            ),
        )

    enforcement_client = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )

    try:
        return await replay_payloads_as_scenario(
            name=body.name,
            tenant_id=body.tenant_id,
            policy_bundle_id=body.policy_bundle_id,
            labelled_payloads=labelled_payloads,
            bundle=bundle,
            enforcement_client=enforcement_client,
        )
    except TabletopError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

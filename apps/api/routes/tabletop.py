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
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import Principal, get_principal
from apps.api.routes.receipts import get_session
from packages.ledger.bundle_repository import get_bundle_by_id
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.policy.tabletop import (
    TabletopError,
    TabletopResult,
    TabletopScenario,
    simulate_scenario,
)

router = APIRouter(prefix="/v1/tabletop", tags=["tabletop"])


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

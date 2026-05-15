"""Tabletop incident-response simulation (CP9.29 / BR-12).

A security engineer asks: "Before I deploy this stricter policy bundle to
production, what would have happened if I had run it against last week's
agent traffic?" Tabletop is the answer: it replays a sequence of synthetic
agent events through a candidate `PolicyEnforcementClient` against a given
`PolicyBundle`, captures the verdicts, and returns a summary - **without
persisting anything, without writing Receipts, without mutating the
chain.**

The output is a `TabletopResult` containing:
  - the original scenario
  - per-event captured `PolicyVerdict` objects
  - aggregate decision counts (allow / deny / escalate / errored)
  - the policy bundle id + version + content_hash actually used (so the
    security engineer can prove later which bundle drove this answer)

Tabletop is a read-only product. It must never:
  - Open a database session
  - Add a Receipt to the ledger
  - Anchor a chain root
  - Mutate the active policy bundle
  - Issue any HTTP call other than the enforcement adapter's evaluate()

The route layer (`apps/api/routes/tabletop.py`) enforces tenant isolation:
the scenario's `tenant_id` must match the authenticated principal's
`tenant_id` and must also match the policy bundle's `tenant_id`. Otherwise
a security engineer at tenant A could probe tenant B's policy bundles by
crafting a tabletop scenario referencing tenant B's bundle id.

PRODUCTION-DEFERRED:
  - NEW-P11.X.tabletop-bundle-from-storage: today the route receives the
    bundle from a `PolicyBundleProvider`; production needs a UI flow to
    select a draft bundle from the approval workflow.
  - NEW-P12.X.tabletop-replay-real-events: today the scenario carries
    synthetic events as inline payloads; production wants the option to
    replay a window of real historical events against a candidate bundle
    (read-only on the ledger).
  - NEW-P12.X.tabletop-diff-report: compare the simulated decisions
    against the actual decisions for the same events under the live
    bundle, surfacing only the diffs.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from packages.policy.enforcement import (
    PolicyDecision,
    PolicyEnforcementClient,
    PolicyEnforcementError,
    PolicyVerdict,
)
from packages.schema.policy_bundle import PolicyBundle


class TabletopError(ValueError):
    """Raised when a tabletop scenario cannot be simulated."""


class TabletopActionSpec(BaseModel):
    """A single synthetic action in a tabletop scenario.

    Mirrors the shape `PolicyEnforcementClient.evaluate()` expects for its
    `action` argument: a dict of arbitrary action fields. The `label` is
    a human-friendly identifier used only in the result so the security
    engineer can match each verdict back to the action that produced it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str = Field(..., min_length=1, max_length=128, description="Human label")
    action: dict[str, Any] = Field(..., description="Action payload for evaluate()")


class TabletopScenario(BaseModel):
    """A named simulation of N synthetic actions against a candidate bundle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(..., min_length=1, max_length=256, description="Scenario name")
    tenant_id: UUID = Field(..., description="Tenant authoring the scenario")
    policy_bundle_id: UUID = Field(..., description="Bundle to simulate against")
    actions: list[TabletopActionSpec] = Field(
        ..., min_length=1, max_length=1000, description="Synthetic actions to replay"
    )


class TabletopActionResult(BaseModel):
    """Per-action outcome inside a TabletopResult."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str = Field(..., description="Mirrors TabletopActionSpec.label")
    decision: PolicyDecision | None = Field(
        ..., description="None when the enforcement adapter errored"
    )
    reason: str | None = Field(..., description="Verdict reason or error message")
    errored: bool = Field(..., description="True iff the enforcement call raised")


class TabletopSummary(BaseModel):
    """Aggregate decision counts across a scenario."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    total: int = Field(..., ge=0)
    allow: int = Field(..., ge=0)
    deny: int = Field(..., ge=0)
    escalate: int = Field(..., ge=0)
    errored: int = Field(..., ge=0)


class TabletopResult(BaseModel):
    """Output of `simulate_scenario()`.

    Carries the scenario, per-action results, the actual bundle metadata
    used (so the answer is auditable), and aggregate counts.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario: TabletopScenario
    bundle_id: UUID
    bundle_version: str
    bundle_content_hash: str = Field(..., min_length=64, max_length=64)
    action_results: list[TabletopActionResult]
    summary: TabletopSummary


async def simulate_scenario(
    *,
    scenario: TabletopScenario,
    bundle: PolicyBundle,
    enforcement_client: PolicyEnforcementClient,
) -> TabletopResult:
    """Replay each action in `scenario` through `enforcement_client`.

    The `bundle` parameter is the candidate policy bundle the security
    engineer wants to evaluate. It must belong to the same tenant as the
    scenario (`TabletopError` otherwise). The `enforcement_client` should
    be configured against this bundle (its evaluate() calls return
    `PolicyVerdict` objects bound to the bundle's id + version +
    content_hash).

    Side effects: NONE. No DB writes, no Receipts, no chain mutation, no
    bundle persistence. The result is computed entirely in memory.

    Adapter errors are captured per-action as `errored=True` results
    rather than aborting the entire scenario. This is the right shape
    for tabletop: a security engineer wants to see which actions would
    have errored alongside which would have been allowed/denied.
    """
    if bundle.tenant_id != scenario.tenant_id:
        raise TabletopError(
            f"bundle.tenant_id ({bundle.tenant_id}) does not match "
            f"scenario.tenant_id ({scenario.tenant_id})"
        )
    if bundle.id != scenario.policy_bundle_id:
        raise TabletopError(
            f"bundle.id ({bundle.id}) does not match "
            f"scenario.policy_bundle_id ({scenario.policy_bundle_id})"
        )

    action_results: list[TabletopActionResult] = []
    counts = {"allow": 0, "deny": 0, "escalate": 0, "errored": 0}

    for spec in scenario.actions:
        try:
            verdict: PolicyVerdict = await enforcement_client.evaluate(
                scenario.tenant_id, spec.action
            )
        except PolicyEnforcementError as exc:
            action_results.append(
                TabletopActionResult(
                    label=spec.label,
                    decision=None,
                    reason=f"enforcement_error: {exc}",
                    errored=True,
                )
            )
            counts["errored"] += 1
            continue

        action_results.append(
            TabletopActionResult(
                label=spec.label,
                decision=verdict.decision,
                reason=verdict.reason,
                errored=False,
            )
        )
        counts[verdict.decision.value] += 1

    summary = TabletopSummary(
        total=len(scenario.actions),
        allow=counts["allow"],
        deny=counts["deny"],
        escalate=counts["escalate"],
        errored=counts["errored"],
    )

    return TabletopResult(
        scenario=scenario,
        bundle_id=bundle.id,
        bundle_version=bundle.version,
        bundle_content_hash=bundle.content_hash,
        action_results=action_results,
        summary=summary,
    )

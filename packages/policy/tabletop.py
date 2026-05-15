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
  - (closed in CP9.38) NEW-P12.X.tabletop-diff-report: compare the
    simulated decisions against the actual decisions for the same events
    under the live bundle, surfacing only the diffs. See
    ``diff_tabletop_results`` + ``TabletopDiffEntry`` + ``TabletopDiffReport``
    at the bottom of this module.
  - (CP9.39 partial close) NEW-P12.X.tabletop-replay-real-events: the
    pure transform ``build_scenario_from_payloads`` + the thin async
    helper ``replay_payloads_as_scenario`` below let a caller turn any
    list of (label, payload) tuples into a TabletopScenario and replay
    it. CP9.40 will add the read-only event-window repository helper +
    route that fetches real historical events and feeds them in.
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


# ---------------------------------------------------------------------------
# CP9.38 / NEW-P12.X.tabletop-diff-report
# ---------------------------------------------------------------------------
#
# A security engineer who has run TWO simulations -- one against the
# proposed bundle, one against the active bundle -- wants to see ONLY the
# actions where the two bundles disagree. This is the operational shape
# of the question "what behaviour would change if I deployed the proposed
# bundle?". A side-by-side table of allow/deny/escalate for all 1000
# actions is overwhelming; a 10-row diff is actionable.
#
# The diff function is pure (no I/O) and operates on TabletopResult or
# list[TabletopActionResult] inputs. It joins the two lists by
# `action_label` and emits per-action drift entries classified as:
#
#   match           -- both sides produced the same decision (omitted from
#                      the report by default; surface only on demand)
#   drift           -- both sides produced a decision, but different ones
#   simulated_only  -- label present in simulated, absent in actual
#   actual_only     -- label present in actual, absent in simulated
#   errored_either  -- at least one side raised; surface the error reason
#
# This is the smallest useful diff vocabulary. A future CP can add
# "materiality scoring" (which drifts matter most) but that requires
# additional context the diff itself doesn't have.


class TabletopDiffEntry(BaseModel):
    """One row in a TabletopDiffReport.

    The ``kind`` discriminator names the relationship between the two sides.
    Fields that don't apply to a kind are None (e.g. ``actual_decision`` is
    None on a ``simulated_only`` row).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str = Field(..., description="Action label being diffed")
    kind: str = Field(
        ...,
        description=("One of: match | drift | simulated_only | actual_only | errored_either"),
    )
    simulated_decision: PolicyDecision | None = Field(
        ..., description="Decision under the simulated (proposed) bundle, None if absent or errored"
    )
    simulated_reason: str | None = Field(..., description="Reason / error from the simulated side")
    actual_decision: PolicyDecision | None = Field(
        ..., description="Decision under the actual (active) bundle, None if absent or errored"
    )
    actual_reason: str | None = Field(..., description="Reason / error from the actual side")


class TabletopDiffReport(BaseModel):
    """Output of ``diff_tabletop_results()``.

    Includes per-label entries plus aggregate counts so callers don't have
    to re-scan to render a header. ``entries`` is sorted by label for
    deterministic output across calls with the same inputs.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    entries: list[TabletopDiffEntry]
    total_simulated: int = Field(..., ge=0)
    total_actual: int = Field(..., ge=0)
    match_count: int = Field(..., ge=0)
    drift_count: int = Field(..., ge=0)
    simulated_only_count: int = Field(..., ge=0)
    actual_only_count: int = Field(..., ge=0)
    errored_either_count: int = Field(..., ge=0)


_DIFF_KIND_MATCH = "match"
_DIFF_KIND_DRIFT = "drift"
_DIFF_KIND_SIM_ONLY = "simulated_only"
_DIFF_KIND_ACT_ONLY = "actual_only"
_DIFF_KIND_ERRORED = "errored_either"


def diff_tabletop_results(
    simulated: TabletopResult | list[TabletopActionResult],
    actual: TabletopResult | list[TabletopActionResult],
    *,
    include_matches: bool = False,
) -> TabletopDiffReport:
    """Join two tabletop result sets by action label and emit per-action drift entries.

    Parameters
    ----------
    simulated
        The simulated (proposed-bundle) result, either a full
        ``TabletopResult`` or its ``.action_results`` list directly.
    actual
        The actual (active-bundle) result, same shape options.
    include_matches
        When False (default), entries with kind="match" are omitted from
        the report's ``entries`` list. They're still counted in
        ``match_count``. When True, all rows are included -- useful for
        full audit trails. The diff use case ("show me only the
        differences") is the False default.

    Returns
    -------
    TabletopDiffReport
        Per-label entries sorted by label, plus aggregate counts.

    Raises
    ------
    TabletopError
        If either side has duplicate labels (the diff join is by label
        and requires uniqueness on each side).
    """
    sim_results = simulated.action_results if isinstance(simulated, TabletopResult) else simulated
    act_results = actual.action_results if isinstance(actual, TabletopResult) else actual

    sim_by_label = _index_by_label(sim_results, "simulated")
    act_by_label = _index_by_label(act_results, "actual")

    all_labels = sorted(set(sim_by_label.keys()) | set(act_by_label.keys()))

    entries: list[TabletopDiffEntry] = []
    counts = {
        _DIFF_KIND_MATCH: 0,
        _DIFF_KIND_DRIFT: 0,
        _DIFF_KIND_SIM_ONLY: 0,
        _DIFF_KIND_ACT_ONLY: 0,
        _DIFF_KIND_ERRORED: 0,
    }

    for label in all_labels:
        sim_row = sim_by_label.get(label)
        act_row = act_by_label.get(label)

        if sim_row is None:
            kind = _DIFF_KIND_ACT_ONLY
        elif act_row is None:
            kind = _DIFF_KIND_SIM_ONLY
        elif sim_row.errored or act_row.errored:
            kind = _DIFF_KIND_ERRORED
        elif sim_row.decision == act_row.decision:
            kind = _DIFF_KIND_MATCH
        else:
            kind = _DIFF_KIND_DRIFT

        counts[kind] += 1

        if kind == _DIFF_KIND_MATCH and not include_matches:
            continue

        entries.append(
            TabletopDiffEntry(
                label=label,
                kind=kind,
                simulated_decision=sim_row.decision if sim_row else None,
                simulated_reason=sim_row.reason if sim_row else None,
                actual_decision=act_row.decision if act_row else None,
                actual_reason=act_row.reason if act_row else None,
            )
        )

    return TabletopDiffReport(
        entries=entries,
        total_simulated=len(sim_results),
        total_actual=len(act_results),
        match_count=counts[_DIFF_KIND_MATCH],
        drift_count=counts[_DIFF_KIND_DRIFT],
        simulated_only_count=counts[_DIFF_KIND_SIM_ONLY],
        actual_only_count=counts[_DIFF_KIND_ACT_ONLY],
        errored_either_count=counts[_DIFF_KIND_ERRORED],
    )


def _index_by_label(
    rows: list[TabletopActionResult], side_name: str
) -> dict[str, TabletopActionResult]:
    """Build a label -> row index, raising on duplicate labels.

    The diff join is by label; duplicate labels on either side make the
    join ambiguous. Raise rather than silently merging.
    """
    out: dict[str, TabletopActionResult] = {}
    for row in rows:
        if row.label in out:
            raise TabletopError(
                f"duplicate label {row.label!r} in {side_name} side -- diff join is by label"
            )
        out[row.label] = row
    return out


# ---------------------------------------------------------------------------
# CP9.39 / NEW-P12.X.tabletop-replay-real-events (pure-transform half)
# ---------------------------------------------------------------------------
#
# The full feature is: "replay a window of real historical events against a
# candidate policy bundle to see what would have happened differently."
# That feature has two halves:
#
#   (1) Read-only fetch of real event payloads for a tenant + time window.
#       This needs a new repository helper + a route. Scoped to CP9.40.
#
#   (2) Pure transform: take a list of (label, payload) tuples and build
#       a TabletopScenario that simulate_scenario() can already consume.
#       This is what CP9.39 provides. No DB, no async, no I/O. Same shape
#       as the diff_tabletop_results helper above.
#
# Why split: CP9.40's repository helper has its own test surface (real
# Postgres assertions, time-window edge cases). Keeping the pure transform
# in its own CP means we can ship the data-shape work today and the I/O
# work next, exactly per the "modularise (CP)" directive. Each CP has its
# own commit, own test surface, own rollback boundary.

_MAX_REPLAY_PAYLOADS = 1000  # matches TabletopScenario.actions max_length


def build_scenario_from_payloads(
    *,
    name: str,
    tenant_id: UUID,
    policy_bundle_id: UUID,
    labelled_payloads: list[tuple[str, dict[str, Any]]],
) -> TabletopScenario:
    """Build a TabletopScenario from raw (label, payload) tuples.

    Pure data-shape transform. No I/O. The intended caller is the CP9.40
    `replay_events_window` route, which fetches real event payloads from
    the ledger, attaches deterministic labels (e.g. "event_<uuid>"), and
    feeds them in. But any caller wanting to construct a TabletopScenario
    from non-inline payloads (CSV import, JSON-Lines bulk, etc.) can use
    this same shape.

    Parameters
    ----------
    name
        Scenario name. Same constraints as TabletopScenario.name (1-256).
    tenant_id
        Tenant authoring the scenario. Same as TabletopScenario.tenant_id.
    policy_bundle_id
        Bundle to simulate against. Same as TabletopScenario.policy_bundle_id.
    labelled_payloads
        List of (label, payload_dict) tuples. Each label must be unique
        (1-128 chars, validated by TabletopActionSpec). Each payload is
        the dict the enforcement client's evaluate() will receive as its
        `action` argument. List length must be 1-1000 (matches
        TabletopScenario.actions bounds).

    Returns
    -------
    TabletopScenario
        A scenario ready to feed to simulate_scenario().

    Raises
    ------
    TabletopError
        If labelled_payloads is empty, exceeds _MAX_REPLAY_PAYLOADS, or
        contains duplicate labels.
    """
    if not labelled_payloads:
        raise TabletopError("labelled_payloads must contain at least one (label, payload) tuple")
    if len(labelled_payloads) > _MAX_REPLAY_PAYLOADS:
        raise TabletopError(
            f"labelled_payloads exceeds maximum {_MAX_REPLAY_PAYLOADS} "
            f"(got {len(labelled_payloads)}); narrow the time window"
        )

    seen_labels: set[str] = set()
    action_specs: list[TabletopActionSpec] = []
    for label, payload in labelled_payloads:
        if label in seen_labels:
            raise TabletopError(
                f"duplicate label {label!r} -- each replayed event needs a unique label"
            )
        seen_labels.add(label)
        # TabletopActionSpec enforces label 1-128 chars + frozen + extra=forbid;
        # validation errors bubble up as pydantic.ValidationError which the
        # route layer maps to 422.
        action_specs.append(TabletopActionSpec(label=label, action=payload))

    return TabletopScenario(
        name=name,
        tenant_id=tenant_id,
        policy_bundle_id=policy_bundle_id,
        actions=action_specs,
    )


async def replay_payloads_as_scenario(
    *,
    name: str,
    tenant_id: UUID,
    policy_bundle_id: UUID,
    labelled_payloads: list[tuple[str, dict[str, Any]]],
    bundle: PolicyBundle,
    enforcement_client: PolicyEnforcementClient,
) -> TabletopResult:
    """Build a scenario from raw payloads, then simulate it.

    Thin async wrapper combining ``build_scenario_from_payloads`` with
    ``simulate_scenario``. Same side-effect contract as simulate_scenario:
    NO DB writes, NO Receipts, NO chain mutation, NO bundle persistence.
    The enforcement client may make HTTP calls to evaluate() depending on
    its concrete implementation.

    Used by the CP9.40 replay-events route to keep the route shape thin:
    fetch payloads (route's responsibility) -> hand to this function
    (transform + simulate happens here) -> return TabletopResult.
    """
    scenario = build_scenario_from_payloads(
        name=name,
        tenant_id=tenant_id,
        policy_bundle_id=policy_bundle_id,
        labelled_payloads=labelled_payloads,
    )
    return await simulate_scenario(
        scenario=scenario,
        bundle=bundle,
        enforcement_client=enforcement_client,
    )

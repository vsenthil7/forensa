"""Tests for tabletop incident-response simulation (CP9.29 / BR-12)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest

from packages.policy.bundle_builder import build_bundle
from packages.policy.enforcement import (
    PolicyDecision,
    PolicyEnforcementClient,
    PolicyEnforcementError,
    PolicyVerdict,
)
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.policy.tabletop import (
    TabletopActionResult,
    TabletopActionSpec,
    TabletopDiffEntry,
    TabletopDiffReport,
    TabletopError,
    TabletopResult,
    TabletopScenario,
    build_scenario_from_payloads,
    diff_tabletop_results,
    replay_payloads_as_scenario,
    simulate_scenario,
)

_TENANT = UUID("12345678-1234-1234-1234-123456789abc")
_OTHER_TENANT = UUID("87654321-4321-4321-4321-cba987654321")
_CONTENT: dict[str, Any] = {
    "rules": [
        {"kind": "deny_kind", "decision": "deny"},
        {"kind": "escalate_kind", "decision": "escalate"},
    ],
    "default": "allow",
}


def _bundle(tenant: UUID = _TENANT):
    return build_bundle(tenant_id=tenant, version="1.0.0", content=_CONTENT)


def _client(bundle):
    return MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )


# ---------- happy path ----------


@pytest.mark.asyncio
async def test_simulate_mixed_decisions() -> None:
    bundle = _bundle()
    client = _client(bundle)
    scenario = TabletopScenario(
        name="quarterly policy review",
        tenant_id=_TENANT,
        policy_bundle_id=bundle.id,
        actions=[
            TabletopActionSpec(label="allow-1", action={"kind": "ok"}),
            TabletopActionSpec(label="deny-1", action={"kind": "deny_kind"}),
            TabletopActionSpec(label="escalate-1", action={"kind": "escalate_kind"}),
            TabletopActionSpec(label="allow-2", action={"kind": "anything_else"}),
        ],
    )
    result = await simulate_scenario(scenario=scenario, bundle=bundle, enforcement_client=client)
    assert isinstance(result, TabletopResult)
    assert result.summary.total == 4
    assert result.summary.allow == 2
    assert result.summary.deny == 1
    assert result.summary.escalate == 1
    assert result.summary.errored == 0
    assert result.bundle_id == bundle.id
    assert result.bundle_version == bundle.version
    assert result.bundle_content_hash == bundle.content_hash
    assert len(result.action_results) == 4
    labels = [ar.label for ar in result.action_results]
    assert labels == ["allow-1", "deny-1", "escalate-1", "allow-2"]


@pytest.mark.asyncio
async def test_simulate_single_action_scenario() -> None:
    bundle = _bundle()
    client = _client(bundle)
    scenario = TabletopScenario(
        name="single-test",
        tenant_id=_TENANT,
        policy_bundle_id=bundle.id,
        actions=[TabletopActionSpec(label="solo", action={"kind": "ok"})],
    )
    result = await simulate_scenario(scenario=scenario, bundle=bundle, enforcement_client=client)
    assert result.summary.total == 1
    assert result.summary.allow == 1
    assert result.action_results[0].decision == PolicyDecision.ALLOW


@pytest.mark.asyncio
async def test_simulate_all_deny_scenario() -> None:
    bundle = _bundle()
    client = _client(bundle)
    scenario = TabletopScenario(
        name="all-deny",
        tenant_id=_TENANT,
        policy_bundle_id=bundle.id,
        actions=[
            TabletopActionSpec(label=f"deny-{i}", action={"kind": "deny_kind"}) for i in range(5)
        ],
    )
    result = await simulate_scenario(scenario=scenario, bundle=bundle, enforcement_client=client)
    assert result.summary.deny == 5
    assert result.summary.allow == 0


# ---------- tenant isolation ----------


@pytest.mark.asyncio
async def test_simulate_rejects_cross_tenant_bundle() -> None:
    """Bundle belongs to one tenant, scenario references another."""
    other_bundle = _bundle(tenant=_OTHER_TENANT)
    client = _client(other_bundle)
    scenario = TabletopScenario(
        name="probe",
        tenant_id=_TENANT,
        policy_bundle_id=other_bundle.id,
        actions=[TabletopActionSpec(label="x", action={"kind": "ok"})],
    )
    with pytest.raises(TabletopError, match="tenant_id"):
        await simulate_scenario(scenario=scenario, bundle=other_bundle, enforcement_client=client)


@pytest.mark.asyncio
async def test_simulate_rejects_mismatched_bundle_id() -> None:
    """Scenario references one bundle id, but a different bundle is passed."""
    bundle = _bundle()
    other_bundle = _bundle()  # different UUID
    client = _client(other_bundle)
    scenario = TabletopScenario(
        name="probe",
        tenant_id=_TENANT,
        policy_bundle_id=bundle.id,  # references the first bundle
        actions=[TabletopActionSpec(label="x", action={"kind": "ok"})],
    )
    with pytest.raises(TabletopError, match="policy_bundle_id"):
        await simulate_scenario(scenario=scenario, bundle=other_bundle, enforcement_client=client)


# ---------- error handling ----------


class _ErroringClient(PolicyEnforcementClient):
    """Adapter that always raises PolicyEnforcementError."""

    async def evaluate(self, tenant_id: UUID, action: dict[str, Any]) -> PolicyVerdict:
        raise PolicyEnforcementError("simulated upstream failure")


@pytest.mark.asyncio
async def test_simulate_captures_enforcement_errors_per_action() -> None:
    bundle = _bundle()
    erroring = _ErroringClient()
    scenario = TabletopScenario(
        name="upstream-failure-drill",
        tenant_id=_TENANT,
        policy_bundle_id=bundle.id,
        actions=[
            TabletopActionSpec(label="a-1", action={"kind": "ok"}),
            TabletopActionSpec(label="a-2", action={"kind": "ok"}),
        ],
    )
    result = await simulate_scenario(scenario=scenario, bundle=bundle, enforcement_client=erroring)
    assert result.summary.errored == 2
    assert result.summary.total == 2
    assert result.summary.allow == 0
    assert result.summary.deny == 0
    assert all(ar.errored is True for ar in result.action_results)
    assert all(ar.decision is None for ar in result.action_results)
    assert all("simulated upstream failure" in (ar.reason or "") for ar in result.action_results)


class _PartiallyErroringClient(PolicyEnforcementClient):
    """First call raises, subsequent calls allow."""

    def __init__(self, bundle):
        self._bundle = bundle
        self._calls = 0

    async def evaluate(self, tenant_id: UUID, action: dict[str, Any]) -> PolicyVerdict:
        self._calls += 1
        if self._calls == 1:
            raise PolicyEnforcementError("transient")
        return PolicyVerdict(
            decision=PolicyDecision.ALLOW,
            policy_bundle_id=self._bundle.id,
            policy_bundle_version=self._bundle.version,
            content_hash=self._bundle.content_hash,
            reason="recovered",
        )


@pytest.mark.asyncio
async def test_simulate_continues_after_partial_error() -> None:
    """A mid-scenario error doesn't abort - other actions still simulate."""
    bundle = _bundle()
    client = _PartiallyErroringClient(bundle)
    scenario = TabletopScenario(
        name="partial-failure",
        tenant_id=_TENANT,
        policy_bundle_id=bundle.id,
        actions=[
            TabletopActionSpec(label="first-errors", action={"kind": "ok"}),
            TabletopActionSpec(label="second-ok", action={"kind": "ok"}),
            TabletopActionSpec(label="third-ok", action={"kind": "ok"}),
        ],
    )
    result = await simulate_scenario(scenario=scenario, bundle=bundle, enforcement_client=client)
    assert result.summary.errored == 1
    assert result.summary.allow == 2
    assert result.summary.total == 3
    assert result.action_results[0].errored is True
    assert result.action_results[1].errored is False
    assert result.action_results[2].errored is False


# ---------- scenario validation ----------


def test_scenario_rejects_empty_actions() -> None:
    bundle = _bundle()
    with pytest.raises(ValueError, match="at least 1"):
        TabletopScenario(
            name="empty",
            tenant_id=_TENANT,
            policy_bundle_id=bundle.id,
            actions=[],
        )


def test_scenario_rejects_too_many_actions() -> None:
    bundle = _bundle()
    with pytest.raises(ValueError, match="at most 1000"):
        TabletopScenario(
            name="too-big",
            tenant_id=_TENANT,
            policy_bundle_id=bundle.id,
            actions=[
                TabletopActionSpec(label=f"a-{i}", action={"kind": "ok"}) for i in range(1001)
            ],
        )


def test_scenario_action_spec_rejects_empty_label() -> None:
    with pytest.raises(ValueError):
        TabletopActionSpec(label="", action={"kind": "ok"})


def test_scenario_action_spec_rejects_extra_fields() -> None:
    """frozen=True + extra=forbid: unknown fields rejected at construction."""
    with pytest.raises(ValueError):
        TabletopActionSpec.model_validate(
            {"label": "x", "action": {"kind": "ok"}, "unknown_field": "boom"}
        )


# ---------- no side effects ----------


@pytest.mark.asyncio
async def test_simulate_does_not_mutate_bundle() -> None:
    """Scenario should not change bundle content_hash, id, version."""
    bundle = _bundle()
    client = _client(bundle)
    original_content_hash = bundle.content_hash
    original_version = bundle.version
    original_id = bundle.id
    scenario = TabletopScenario(
        name="readonly-check",
        tenant_id=_TENANT,
        policy_bundle_id=bundle.id,
        actions=[
            TabletopActionSpec(label="a", action={"kind": "deny_kind"}),
            TabletopActionSpec(label="b", action={"kind": "ok"}),
        ],
    )
    _ = await simulate_scenario(scenario=scenario, bundle=bundle, enforcement_client=client)
    # Bundle is a frozen Pydantic model so mutation would have raised; this
    # guards against any future refactor that loses the frozen=True.
    assert bundle.content_hash == original_content_hash
    assert bundle.version == original_version
    assert bundle.id == original_id


@pytest.mark.asyncio
async def test_simulate_result_carries_bundle_metadata_for_audit() -> None:
    """A security engineer can prove later which bundle drove the answer."""
    bundle = _bundle()
    client = _client(bundle)
    scenario = TabletopScenario(
        name="audit-trail",
        tenant_id=_TENANT,
        policy_bundle_id=bundle.id,
        actions=[TabletopActionSpec(label="a", action={"kind": "ok"})],
    )
    result = await simulate_scenario(scenario=scenario, bundle=bundle, enforcement_client=client)
    assert result.bundle_id == bundle.id
    assert result.bundle_version == bundle.version
    assert result.bundle_content_hash == bundle.content_hash
    assert len(result.bundle_content_hash) == 64


# ---------- CP9.38 / NEW-P12.X.tabletop-diff-report ----------
#
# diff_tabletop_results joins two TabletopResult action lists by label and
# classifies each label as match | drift | simulated_only | actual_only |
# errored_either. The default `include_matches=False` shows only the
# differences (operational shape). These tests cover every kind + the
# duplicate-label guard + the include_matches=True audit-trail mode.


def _row(
    label: str, decision: PolicyDecision | None, reason: str | None = None, errored: bool = False
) -> TabletopActionResult:
    return TabletopActionResult(
        label=label, decision=decision, reason=reason or "", errored=errored
    )


def test_diff_all_match_returns_empty_entries_by_default() -> None:
    sim = [_row("a", PolicyDecision.ALLOW), _row("b", PolicyDecision.DENY)]
    act = [_row("a", PolicyDecision.ALLOW), _row("b", PolicyDecision.DENY)]
    report = diff_tabletop_results(sim, act)
    assert report.match_count == 2
    assert report.drift_count == 0
    assert report.entries == []
    assert report.total_simulated == 2
    assert report.total_actual == 2


def test_diff_all_match_with_include_matches_emits_all_entries() -> None:
    sim = [_row("a", PolicyDecision.ALLOW), _row("b", PolicyDecision.DENY)]
    act = [_row("a", PolicyDecision.ALLOW), _row("b", PolicyDecision.DENY)]
    report = diff_tabletop_results(sim, act, include_matches=True)
    assert report.match_count == 2
    assert len(report.entries) == 2
    assert all(e.kind == "match" for e in report.entries)


def test_diff_drift_surfaces_decision_change() -> None:
    """Same label, different decision -> drift."""
    sim = [_row("a", PolicyDecision.DENY, reason="proposed-blocks")]
    act = [_row("a", PolicyDecision.ALLOW, reason="active-allows")]
    report = diff_tabletop_results(sim, act)
    assert report.drift_count == 1
    assert len(report.entries) == 1
    entry = report.entries[0]
    assert entry.label == "a"
    assert entry.kind == "drift"
    assert entry.simulated_decision == PolicyDecision.DENY
    assert entry.actual_decision == PolicyDecision.ALLOW
    assert entry.simulated_reason == "proposed-blocks"
    assert entry.actual_reason == "active-allows"


def test_diff_simulated_only_when_label_absent_from_actual() -> None:
    sim = [_row("new-label", PolicyDecision.DENY)]
    act: list[TabletopActionResult] = []
    report = diff_tabletop_results(sim, act)
    assert report.simulated_only_count == 1
    assert len(report.entries) == 1
    entry = report.entries[0]
    assert entry.kind == "simulated_only"
    assert entry.simulated_decision == PolicyDecision.DENY
    assert entry.actual_decision is None
    assert entry.actual_reason is None


def test_diff_actual_only_when_label_absent_from_simulated() -> None:
    sim: list[TabletopActionResult] = []
    act = [_row("orphan", PolicyDecision.ALLOW)]
    report = diff_tabletop_results(sim, act)
    assert report.actual_only_count == 1
    assert len(report.entries) == 1
    entry = report.entries[0]
    assert entry.kind == "actual_only"
    assert entry.simulated_decision is None
    assert entry.actual_decision == PolicyDecision.ALLOW


def test_diff_errored_either_when_simulated_side_errored() -> None:
    sim = [_row("a", None, reason="enforcement_error: oops", errored=True)]
    act = [_row("a", PolicyDecision.ALLOW)]
    report = diff_tabletop_results(sim, act)
    assert report.errored_either_count == 1
    assert len(report.entries) == 1
    entry = report.entries[0]
    assert entry.kind == "errored_either"
    assert entry.simulated_decision is None
    assert entry.actual_decision == PolicyDecision.ALLOW


def test_diff_errored_either_when_actual_side_errored() -> None:
    sim = [_row("a", PolicyDecision.ALLOW)]
    act = [_row("a", None, reason="enforcement_error: oops", errored=True)]
    report = diff_tabletop_results(sim, act)
    assert report.errored_either_count == 1
    assert report.entries[0].kind == "errored_either"


def test_diff_entries_sorted_by_label_for_deterministic_output() -> None:
    sim = [
        _row("z", PolicyDecision.DENY),
        _row("a", PolicyDecision.DENY),
        _row("m", PolicyDecision.DENY),
    ]
    act = [
        _row("z", PolicyDecision.ALLOW),
        _row("a", PolicyDecision.ALLOW),
        _row("m", PolicyDecision.ALLOW),
    ]
    report = diff_tabletop_results(sim, act)
    labels = [e.label for e in report.entries]
    assert labels == sorted(labels)
    assert labels == ["a", "m", "z"]


def test_diff_rejects_duplicate_labels_on_simulated_side() -> None:
    sim = [
        _row("dup", PolicyDecision.ALLOW),
        _row("dup", PolicyDecision.DENY),
    ]
    act = [_row("dup", PolicyDecision.ALLOW)]
    with pytest.raises(TabletopError, match="duplicate label"):
        diff_tabletop_results(sim, act)


def test_diff_rejects_duplicate_labels_on_actual_side() -> None:
    sim = [_row("dup", PolicyDecision.ALLOW)]
    act = [
        _row("dup", PolicyDecision.ALLOW),
        _row("dup", PolicyDecision.DENY),
    ]
    with pytest.raises(TabletopError, match="duplicate label"):
        diff_tabletop_results(sim, act)


@pytest.mark.asyncio
async def test_diff_accepts_tabletop_result_objects_directly() -> None:
    """diff_tabletop_results accepts TabletopResult or list[TabletopActionResult]."""
    bundle = _bundle()
    client = _client(bundle)
    scenario = TabletopScenario(
        name="s1",
        tenant_id=_TENANT,
        policy_bundle_id=bundle.id,
        actions=[
            TabletopActionSpec(label="a", action={"kind": "deny_kind"}),
            TabletopActionSpec(label="b", action={"kind": "ok"}),
        ],
    )
    sim_result = await simulate_scenario(
        scenario=scenario, bundle=bundle, enforcement_client=client
    )
    act_result = await simulate_scenario(
        scenario=scenario, bundle=bundle, enforcement_client=client
    )
    # Same bundle + same scenario -> all match.
    report = diff_tabletop_results(sim_result, act_result)
    assert report.match_count == 2
    assert report.drift_count == 0
    assert report.entries == []


def test_diff_mixed_report_classifies_every_label_correctly() -> None:
    """End-to-end: every diff kind in one report."""
    sim = [
        _row("matches", PolicyDecision.ALLOW),
        _row("drifts", PolicyDecision.DENY),
        _row("only-sim", PolicyDecision.ESCALATE),
        _row("both-errored", None, reason="err", errored=True),
    ]
    act = [
        _row("matches", PolicyDecision.ALLOW),
        _row("drifts", PolicyDecision.ALLOW),
        _row("only-act", PolicyDecision.DENY),
        _row("both-errored", PolicyDecision.ALLOW),
    ]
    report = diff_tabletop_results(sim, act)
    # Counts.
    assert report.match_count == 1
    assert report.drift_count == 1
    assert report.simulated_only_count == 1
    assert report.actual_only_count == 1
    assert report.errored_either_count == 1
    # Entries (no matches by default) -> 4 entries.
    assert len(report.entries) == 4
    kinds = {e.label: e.kind for e in report.entries}
    assert kinds["drifts"] == "drift"
    assert kinds["only-sim"] == "simulated_only"
    assert kinds["only-act"] == "actual_only"
    assert kinds["both-errored"] == "errored_either"


def test_diff_entry_and_report_are_frozen() -> None:
    sim = [_row("a", PolicyDecision.ALLOW)]
    act = [_row("a", PolicyDecision.DENY)]
    report = diff_tabletop_results(sim, act)
    assert isinstance(report, TabletopDiffReport)
    assert isinstance(report.entries[0], TabletopDiffEntry)
    # Frozen: mutation raises.
    with pytest.raises(ValueError):
        report.entries[0].label = "changed"  # type: ignore[misc]
    with pytest.raises(ValueError):
        report.match_count = 99  # type: ignore[misc]


# ---------- CP9.39 / NEW-P12.X.tabletop-replay-real-events (pure-transform half) ----------
#
# build_scenario_from_payloads is a pure transform: turn (label, payload)
# tuples into a TabletopScenario. replay_payloads_as_scenario is the thin
# async wrapper that simulates the constructed scenario. The CP9.40 route
# layer will fetch real event payloads from the ledger and feed them in.
# These tests cover the pure transform's validation + the wrapper's
# behaviour, NOT the eventual ledger-read path.


def test_build_scenario_from_payloads_happy_path() -> None:
    bundle = _bundle()
    payloads = [
        ("event-1", {"kind": "ok"}),
        ("event-2", {"kind": "deny_kind"}),
        ("event-3", {"kind": "escalate_kind"}),
    ]
    scenario = build_scenario_from_payloads(
        name="replay-week-21",
        tenant_id=_TENANT,
        policy_bundle_id=bundle.id,
        labelled_payloads=payloads,
    )
    assert isinstance(scenario, TabletopScenario)
    assert scenario.name == "replay-week-21"
    assert scenario.tenant_id == _TENANT
    assert scenario.policy_bundle_id == bundle.id
    assert len(scenario.actions) == 3
    assert [a.label for a in scenario.actions] == ["event-1", "event-2", "event-3"]
    assert scenario.actions[1].action == {"kind": "deny_kind"}


def test_build_scenario_preserves_payload_order() -> None:
    """Replaying real events in chronological order matters; the transform
    must not reorder."""
    bundle = _bundle()
    payloads = [(f"event-{i:03d}", {"kind": "ok", "i": i}) for i in range(10)]
    scenario = build_scenario_from_payloads(
        name="order-check",
        tenant_id=_TENANT,
        policy_bundle_id=bundle.id,
        labelled_payloads=payloads,
    )
    expected_labels = [f"event-{i:03d}" for i in range(10)]
    assert [a.label for a in scenario.actions] == expected_labels


def test_build_scenario_rejects_empty_payload_list() -> None:
    bundle = _bundle()
    with pytest.raises(TabletopError, match="at least one"):
        build_scenario_from_payloads(
            name="empty",
            tenant_id=_TENANT,
            policy_bundle_id=bundle.id,
            labelled_payloads=[],
        )


def test_build_scenario_rejects_too_many_payloads() -> None:
    bundle = _bundle()
    too_many = [(f"e-{i}", {"kind": "ok"}) for i in range(1001)]
    with pytest.raises(TabletopError, match="exceeds maximum 1000"):
        build_scenario_from_payloads(
            name="too-big",
            tenant_id=_TENANT,
            policy_bundle_id=bundle.id,
            labelled_payloads=too_many,
        )


def test_build_scenario_rejects_duplicate_labels() -> None:
    bundle = _bundle()
    with pytest.raises(TabletopError, match="duplicate label"):
        build_scenario_from_payloads(
            name="dup",
            tenant_id=_TENANT,
            policy_bundle_id=bundle.id,
            labelled_payloads=[
                ("dup", {"kind": "ok"}),
                ("dup", {"kind": "deny_kind"}),
            ],
        )


def test_build_scenario_propagates_action_spec_validation_for_empty_label() -> None:
    """TabletopActionSpec.label has min_length=1; an empty label bubbles up
    as a Pydantic ValidationError, which the route layer maps to 422."""
    bundle = _bundle()
    with pytest.raises(ValueError):
        build_scenario_from_payloads(
            name="bad-label",
            tenant_id=_TENANT,
            policy_bundle_id=bundle.id,
            labelled_payloads=[("", {"kind": "ok"})],
        )


def test_build_scenario_at_exactly_1000_payloads_is_allowed() -> None:
    """Boundary check: _MAX_REPLAY_PAYLOADS is inclusive at 1000."""
    bundle = _bundle()
    exactly_max = [(f"e-{i:04d}", {"kind": "ok"}) for i in range(1000)]
    scenario = build_scenario_from_payloads(
        name="max-size",
        tenant_id=_TENANT,
        policy_bundle_id=bundle.id,
        labelled_payloads=exactly_max,
    )
    assert len(scenario.actions) == 1000


@pytest.mark.asyncio
async def test_replay_payloads_as_scenario_end_to_end() -> None:
    """The thin async wrapper combines build + simulate; verify the result."""
    bundle = _bundle()
    client = _client(bundle)
    payloads = [
        ("replay-1", {"kind": "ok"}),
        ("replay-2", {"kind": "deny_kind"}),
        ("replay-3", {"kind": "escalate_kind"}),
    ]
    result = await replay_payloads_as_scenario(
        name="end-to-end",
        tenant_id=_TENANT,
        policy_bundle_id=bundle.id,
        labelled_payloads=payloads,
        bundle=bundle,
        enforcement_client=client,
    )
    assert isinstance(result, TabletopResult)
    assert result.scenario.name == "end-to-end"
    assert result.summary.total == 3
    assert result.summary.allow == 1
    assert result.summary.deny == 1
    assert result.summary.escalate == 1
    # Labels round-trip from payloads through scenario into action_results.
    labels = [ar.label for ar in result.action_results]
    assert labels == ["replay-1", "replay-2", "replay-3"]


@pytest.mark.asyncio
async def test_replay_payloads_propagates_tenant_mismatch_via_simulate() -> None:
    """replay_payloads_as_scenario calls simulate_scenario which enforces
    bundle.tenant_id == scenario.tenant_id. If the caller passes a bundle
    from a different tenant, the simulate layer raises TabletopError."""
    other_bundle = _bundle(tenant=_OTHER_TENANT)
    client = _client(other_bundle)
    with pytest.raises(TabletopError, match="tenant_id"):
        await replay_payloads_as_scenario(
            name="cross-tenant",
            tenant_id=_TENANT,
            policy_bundle_id=other_bundle.id,
            labelled_payloads=[("e", {"kind": "ok"})],
            bundle=other_bundle,
            enforcement_client=client,
        )


@pytest.mark.asyncio
async def test_replay_then_diff_against_inline_scenario() -> None:
    """Realistic flow: replay real events under proposed bundle, run an
    inline scenario under active bundle, diff the two results.

    This is the operational shape CP9.40 + the diff CP enable: take the
    same events, evaluate under two different bundles, see ONLY the
    decisions that changed."""
    bundle = _bundle()
    client = _client(bundle)
    payloads = [
        ("e-1", {"kind": "ok"}),
        ("e-2", {"kind": "deny_kind"}),
    ]
    replayed = await replay_payloads_as_scenario(
        name="replay",
        tenant_id=_TENANT,
        policy_bundle_id=bundle.id,
        labelled_payloads=payloads,
        bundle=bundle,
        enforcement_client=client,
    )
    # Run the same actions inline as the "actual" side. Same bundle ->
    # same decisions -> diff should report zero drifts.
    inline_scenario = TabletopScenario(
        name="actual",
        tenant_id=_TENANT,
        policy_bundle_id=bundle.id,
        actions=[TabletopActionSpec(label=lbl, action=p) for lbl, p in payloads],
    )
    actual = await simulate_scenario(
        scenario=inline_scenario, bundle=bundle, enforcement_client=client
    )
    report = diff_tabletop_results(replayed, actual)
    assert report.drift_count == 0
    assert report.match_count == 2
    assert report.entries == []

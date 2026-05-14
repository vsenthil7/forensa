"""Tests for packages.ledger.bundle_workflow (CP9.15 / NEW-P9.8.X.bundle-approval-workflow).

Covers:

- Full happy path: propose -> review -> approve -> activate (call-by-call
  verification of approval rows + bundle status mutations)
- Each transition's reject-bad-source-state branch
- Reason validation: empty string + whitespace-only rejected
- BundleNotFoundError on missing bundle id
- supersede() can be called on an active bundle
- supersede() rejects non-active source
- activate() supersedes a prior active bundle
- list_approvals_for_bundle returns chronological history

Uses MagicMock sessions (no real DB) - the workflow's interactions are
direct enough that mocking is reliable and avoids adding a new dev
dependency (``aiosqlite``). The mock represents the bundle as a tracked
``MagicMock`` with mutable attributes; the test sets up a side_effect on
``scalar_one_or_none`` that returns the bundle (or None) according to an
explicit per-call directive list.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from packages.ledger.bundle_workflow import (
    BundleNotFoundError,
    BundleWorkflowError,
    activate,
    approve,
    list_approvals_for_bundle,
    propose,
    review,
    supersede,
)
from packages.ledger.models import PolicyBundleApprovalRow, PolicyBundleRow

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_bundle_mock(
    *,
    bundle_id: UUID,
    tenant_id: UUID,
    status: str = "proposed",
) -> MagicMock:
    """Return a MagicMock shaped like PolicyBundleRow with mutable ``status``."""
    row = MagicMock(spec=PolicyBundleRow)
    row.id = bundle_id
    row.tenant_id = tenant_id
    row.status = status  # workflow mutates this in place
    return row


def _make_session(
    *,
    scalar_returns: list,
    captured_added: list | None = None,
) -> MagicMock:
    """Mock session whose ``scalar_one_or_none`` follows ``scalar_returns`` in order.

    ``captured_added`` accumulates rows passed to ``session.add`` so tests
    can inspect approval rows + bundle row mutations.
    """
    if captured_added is None:
        captured_added = []

    iterator = iter(scalar_returns)

    def _next_return():
        try:
            return next(iterator)
        except StopIteration:  # pragma: no cover - test author error
            raise AssertionError("scalar_one_or_none called more times than expected") from None

    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(side_effect=_next_return)
    scalars_mock = MagicMock()

    def _scalars_all_factory():
        # Each call returns whatever was just set up via scalar_returns
        # peek - but list_approvals_for_bundle uses result.scalars().all()
        # not scalar_one_or_none, so this is set separately below per test.
        return []

    scalars_mock.all = MagicMock(side_effect=_scalars_all_factory)
    result_mock.scalars = MagicMock(return_value=scalars_mock)

    session = MagicMock()
    session.execute = AsyncMock(return_value=result_mock)
    session.add = MagicMock(side_effect=lambda row: captured_added.append(row))
    session.flush = AsyncMock(return_value=None)
    return session


# ---------------------------------------------------------------------------
# Happy path: propose -> review -> approve -> activate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_workflow_propose_review_approve_activate():
    tid = uuid4()
    bid = uuid4()
    bundle = _make_bundle_mock(bundle_id=bid, tenant_id=tid, status="proposed")

    # Build a custom session because the activate step is special - it
    # queries scalar_one_or_none twice in one call (once for _load_bundle,
    # once to find prior active bundle).
    captured: list = []
    # Sequence of scalar_one_or_none returns matching each step:
    #   propose: _load_bundle -> bundle
    #   review:  _load_bundle -> bundle
    #   approve: _load_bundle -> bundle
    #   activate: _load_bundle -> bundle (status=approved by now)
    #   activate: prior-active lookup -> None
    #   activate: _transition's _load_bundle -> bundle
    session = _make_session(
        scalar_returns=[bundle, bundle, bundle, bundle, None, bundle],
        captured_added=captured,
    )

    author = uuid4()
    reviewer = uuid4()
    approver = uuid4()
    activator = uuid4()

    await propose(session, bundle_id=bid, author_actor_id=author, reason="initial proposal")
    await review(session, bundle_id=bid, reviewer_actor_id=reviewer, reason="LGTM")
    await approve(session, bundle_id=bid, approver_actor_id=approver, reason="sign off")
    await activate(session, bundle_id=bid, activator_actor_id=activator, reason="go live")

    # Verify approval rows written in correct order
    approval_rows = [r for r in captured if isinstance(r, PolicyBundleApprovalRow)]
    assert len(approval_rows) == 4
    transitions = [(a.from_status, a.to_status) for a in approval_rows]
    assert transitions == [
        ("proposed", "proposed"),
        ("proposed", "reviewed"),
        ("reviewed", "approved"),
        ("approved", "active"),
    ]
    # Verify bundle status was mutated to 'active' through the chain
    assert bundle.status == "active"


# ---------------------------------------------------------------------------
# Each transition rejects wrong source state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_rejects_non_proposed_state():
    tid = uuid4()
    bid = uuid4()
    bundle = _make_bundle_mock(bundle_id=bid, tenant_id=tid, status="reviewed")
    session = _make_session(scalar_returns=[bundle])
    with pytest.raises(BundleWorkflowError, match="invalid transition"):
        await review(session, bundle_id=bid, reviewer_actor_id=uuid4(), reason="again")


@pytest.mark.asyncio
async def test_approve_rejects_non_reviewed_state():
    tid = uuid4()
    bid = uuid4()
    bundle = _make_bundle_mock(bundle_id=bid, tenant_id=tid, status="proposed")
    session = _make_session(scalar_returns=[bundle])
    with pytest.raises(BundleWorkflowError, match="invalid transition"):
        await approve(session, bundle_id=bid, approver_actor_id=uuid4(), reason="skip")


@pytest.mark.asyncio
async def test_activate_rejects_non_approved_state():
    tid = uuid4()
    bid = uuid4()
    bundle = _make_bundle_mock(bundle_id=bid, tenant_id=tid, status="reviewed")
    session = _make_session(scalar_returns=[bundle])
    with pytest.raises(BundleWorkflowError, match="requires bundle.status == 'approved'"):
        await activate(session, bundle_id=bid, activator_actor_id=uuid4(), reason="early")


@pytest.mark.asyncio
async def test_propose_rejects_non_proposed_state():
    tid = uuid4()
    bid = uuid4()
    bundle = _make_bundle_mock(bundle_id=bid, tenant_id=tid, status="reviewed")
    session = _make_session(scalar_returns=[bundle])
    with pytest.raises(BundleWorkflowError, match="requires bundle.status == 'proposed'"):
        await propose(session, bundle_id=bid, author_actor_id=uuid4(), reason="again")


# ---------------------------------------------------------------------------
# Reason validation and BundleNotFoundError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_requires_non_empty_reason():
    tid = uuid4()
    bid = uuid4()
    bundle = _make_bundle_mock(bundle_id=bid, tenant_id=tid, status="proposed")
    session = _make_session(scalar_returns=[bundle])
    with pytest.raises(BundleWorkflowError, match="reason is required"):
        await review(session, bundle_id=bid, reviewer_actor_id=uuid4(), reason="")


@pytest.mark.asyncio
async def test_review_requires_non_whitespace_reason():
    tid = uuid4()
    bid = uuid4()
    bundle = _make_bundle_mock(bundle_id=bid, tenant_id=tid, status="proposed")
    session = _make_session(scalar_returns=[bundle])
    with pytest.raises(BundleWorkflowError, match="reason is required"):
        await review(session, bundle_id=bid, reviewer_actor_id=uuid4(), reason="   ")


@pytest.mark.asyncio
async def test_review_raises_bundle_not_found_for_unknown_id():
    unknown = uuid4()
    session = _make_session(scalar_returns=[None])
    with pytest.raises(BundleNotFoundError, match=str(unknown)):
        await review(session, bundle_id=unknown, reviewer_actor_id=uuid4(), reason="x")


@pytest.mark.asyncio
async def test_propose_raises_bundle_not_found_for_unknown_id():
    unknown = uuid4()
    session = _make_session(scalar_returns=[None])
    with pytest.raises(BundleNotFoundError):
        await propose(session, bundle_id=unknown, author_actor_id=uuid4(), reason="x")


# ---------------------------------------------------------------------------
# activate() supersedes prior active bundle in same flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activate_supersedes_prior_active_bundle():
    tid = uuid4()
    new_bid = uuid4()
    old_bid = uuid4()
    new_bundle = _make_bundle_mock(bundle_id=new_bid, tenant_id=tid, status="approved")
    old_bundle = _make_bundle_mock(bundle_id=old_bid, tenant_id=tid, status="active")

    captured: list = []
    # Call sequence inside activate(new_bid):
    #   1. _load_bundle(new_bid) -> new_bundle (status=approved)
    #   2. prior-active lookup -> old_bundle (status=active, found)
    #     - writes 'active'->'superseded' approval row for old_bundle
    #     - mutates old_bundle.status = 'superseded'
    #   3. _transition's _load_bundle(new_bid) -> new_bundle
    session = _make_session(
        scalar_returns=[new_bundle, old_bundle, new_bundle], captured_added=captured
    )

    await activate(session, bundle_id=new_bid, activator_actor_id=uuid4(), reason="rollout")

    # Old bundle must be flipped to 'superseded'
    assert old_bundle.status == "superseded"
    # New bundle must be flipped to 'active'
    assert new_bundle.status == "active"
    # Two approval rows added: one for the supersede, one for the activate
    approval_rows = [r for r in captured if isinstance(r, PolicyBundleApprovalRow)]
    assert len(approval_rows) == 2
    transitions = [(a.from_status, a.to_status) for a in approval_rows]
    assert transitions == [("active", "superseded"), ("approved", "active")]
    # Supersede row references the OLD bundle, activate references the NEW
    assert approval_rows[0].bundle_id == old_bid
    assert approval_rows[1].bundle_id == new_bid
    # System actor on auto-supersede
    assert approval_rows[0].actor_role == "system"
    assert "automatically superseded" in approval_rows[0].reason


# ---------------------------------------------------------------------------
# supersede() manual revocation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_supersede_active_bundle_directly():
    tid = uuid4()
    bid = uuid4()
    bundle = _make_bundle_mock(bundle_id=bid, tenant_id=tid, status="active")
    captured: list = []
    session = _make_session(scalar_returns=[bundle], captured_added=captured)

    await supersede(session, bundle_id=bid, actor_id=uuid4(), reason="security incident")

    assert bundle.status == "superseded"
    approval_rows = [r for r in captured if isinstance(r, PolicyBundleApprovalRow)]
    assert len(approval_rows) == 1
    assert approval_rows[0].from_status == "active"
    assert approval_rows[0].to_status == "superseded"
    assert approval_rows[0].reason == "security incident"


@pytest.mark.asyncio
async def test_supersede_rejects_non_active_state():
    tid = uuid4()
    bid = uuid4()
    bundle = _make_bundle_mock(bundle_id=bid, tenant_id=tid, status="proposed")
    session = _make_session(scalar_returns=[bundle])
    with pytest.raises(BundleWorkflowError, match="invalid transition"):
        await supersede(session, bundle_id=bid, actor_id=uuid4(), reason="too early")


# ---------------------------------------------------------------------------
# list_approvals_for_bundle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_approvals_returns_empty_when_none():
    bid = uuid4()
    # list_approvals_for_bundle uses result.scalars().all() - not
    # scalar_one_or_none. Build a session whose scalars().all() returns [].
    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=[])
    result_mock = MagicMock()
    result_mock.scalars = MagicMock(return_value=scalars_mock)
    session = MagicMock()
    session.execute = AsyncMock(return_value=result_mock)

    approvals = await list_approvals_for_bundle(session, bid)
    assert approvals == []


@pytest.mark.asyncio
async def test_list_approvals_returns_rows_in_session_order():
    """The function passes through ORDER BY decided_at ASC; we trust the SQL
    and verify the row pass-through."""
    bid = uuid4()
    tid = uuid4()
    # Make three real approval rows in chronological order
    rows = [
        PolicyBundleApprovalRow(
            id=uuid4(),
            bundle_id=bid,
            tenant_id=tid,
            from_status="proposed",
            to_status="reviewed",
            actor_id=uuid4(),
            actor_role="reviewer",
            reason="r1",
            decided_at=datetime(2026, 5, 14, 10, 0, tzinfo=UTC),
        ),
        PolicyBundleApprovalRow(
            id=uuid4(),
            bundle_id=bid,
            tenant_id=tid,
            from_status="reviewed",
            to_status="approved",
            actor_id=uuid4(),
            actor_role="approver",
            reason="r2",
            decided_at=datetime(2026, 5, 14, 11, 0, tzinfo=UTC),
        ),
        PolicyBundleApprovalRow(
            id=uuid4(),
            bundle_id=bid,
            tenant_id=tid,
            from_status="approved",
            to_status="active",
            actor_id=uuid4(),
            actor_role="activator",
            reason="r3",
            decided_at=datetime(2026, 5, 14, 12, 0, tzinfo=UTC),
        ),
    ]
    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=rows)
    result_mock = MagicMock()
    result_mock.scalars = MagicMock(return_value=scalars_mock)
    session = MagicMock()
    session.execute = AsyncMock(return_value=result_mock)

    approvals = await list_approvals_for_bundle(session, bid)
    assert [a.to_status for a in approvals] == ["reviewed", "approved", "active"]

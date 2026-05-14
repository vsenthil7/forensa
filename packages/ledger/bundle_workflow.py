"""Bundle approval workflow state machine (CP9.15 / NEW-P9.8.X.bundle-approval-workflow).

Closes the EnterpriseGradeReview 3.16 finding "No policy approval workflow.
Bundle creation is a single function call. Enterprise needs change-management:
proposed -> reviewed -> approved -> activated, with each step audit-logged."

The state machine has five states and forward-only transitions:

::

    proposed --review--> reviewed --approve--> approved --activate--> active
                                                                        |
                                                                        v
                                                                    superseded

Rules:

- ``proposed`` is the entry state (bundles default to it on write).
- ``reviewed`` requires the actor role ``reviewer``. The author cannot
  review their own bundle - this is the segregation-of-duties point of
  having two states. Author identity is the ``actor_id`` of the implicit
  ``proposed`` row (system-emitted at bundle creation; see ``propose``
  below).
- ``approved`` requires the actor role ``approver``. Approver must differ
  from the reviewer for the same reason.
- ``active`` is the unique terminal-but-replaceable state per tenant. The
  DB ``uq_policy_bundles_one_active_per_tenant`` partial UNIQUE index
  enforces "at most one active per tenant".
- Activating a new bundle automatically transitions the prior active bundle
  to ``superseded`` (single transaction, FK-respecting order). If no prior
  active bundle exists, the activation is solo.
- ``superseded`` is terminal: no further transitions allowed.

Every transition writes one ``PolicyBundleApprovalRow``. The transitions
are append-only; ``PolicyBundleRow.status`` is mutated to reflect the new
state but the approval rows themselves preserve the full chronological
history.

Out of scope for this CP (tracked as later items):

- Per-step actor authentication (``actor_id`` is opaque today). CP10.x.
- Bundle-approval rows emitting their own Forensa Receipts (eat your own
  dogfood). ``NEW-P9.15.bundle-approval-receipts``.
- REST surface (``POST /v1/policy-bundles/{id}/approve`` etc.). CP9.16.
- Author <-> reviewer <-> approver segregation enforced at the row level
  (today it's the caller's responsibility). ``NEW-P9.15.segregation-of-duties``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Final
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.ledger.models import PolicyBundleApprovalRow, PolicyBundleRow

# Allowed state machine transitions. Forward-only.
_VALID_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "proposed": frozenset({"reviewed"}),
    "reviewed": frozenset({"approved"}),
    "approved": frozenset({"active"}),
    "active": frozenset({"superseded"}),
    "superseded": frozenset(),  # terminal
}

# Role required to make each transition. None means system-emitted (the
# implicit ``proposed`` row at bundle creation).
_REQUIRED_ROLE: Final[dict[str, str]] = {
    "reviewed": "reviewer",
    "approved": "approver",
    "active": "activator",
    "superseded": "system",
}


class BundleWorkflowError(ValueError):
    """Raised when a transition is invalid (bad source state, missing bundle,
    wrong target state, missing reason)."""


class BundleNotFoundError(BundleWorkflowError):
    """Raised when the bundle id passed to a transition does not exist."""


async def propose(
    session: AsyncSession,
    *,
    bundle_id: UUID,
    author_actor_id: UUID | None,
    reason: str,
) -> UUID:
    """Emit the implicit initial approval row for a freshly-created bundle.

    Called by ``bundle_repository.write_bundle`` (or its callers) right
    after the bundle row is inserted. The approval row's ``from_status`` is
    set to the same as ``to_status`` (``proposed``) - this is the only
    self-transition we allow and it exists purely so the history table has
    a complete record of "who authored this bundle and when".

    Returns the new approval row's id.
    """
    bundle = await _load_bundle(session, bundle_id)
    if bundle.status != "proposed":
        raise BundleWorkflowError(
            f"propose() requires bundle.status == 'proposed', got {bundle.status!r}"
        )
    return await _write_approval(
        session,
        bundle=bundle,
        from_status="proposed",
        to_status="proposed",
        actor_id=author_actor_id,
        actor_role="author",
        reason=reason,
    )


async def review(
    session: AsyncSession,
    *,
    bundle_id: UUID,
    reviewer_actor_id: UUID,
    reason: str,
) -> UUID:
    """Transition a ``proposed`` bundle to ``reviewed``."""
    return await _transition(
        session,
        bundle_id=bundle_id,
        target_status="reviewed",
        actor_id=reviewer_actor_id,
        reason=reason,
    )


async def approve(
    session: AsyncSession,
    *,
    bundle_id: UUID,
    approver_actor_id: UUID,
    reason: str,
) -> UUID:
    """Transition a ``reviewed`` bundle to ``approved``."""
    return await _transition(
        session,
        bundle_id=bundle_id,
        target_status="approved",
        actor_id=approver_actor_id,
        reason=reason,
    )


async def activate(
    session: AsyncSession,
    *,
    bundle_id: UUID,
    activator_actor_id: UUID,
    reason: str,
) -> UUID:
    """Transition an ``approved`` bundle to ``active``.

    If the tenant already has an active bundle, automatically supersede it
    in the same transaction (FK-respecting order: supersede first, then
    activate). The DB ``uq_policy_bundles_one_active_per_tenant`` partial
    UNIQUE index will reject concurrent activations of two bundles to the
    same tenant - one wins, the other gets ``IntegrityError`` which the
    caller should retry or surface as ``BundleWorkflowError``.
    """
    bundle = await _load_bundle(session, bundle_id)
    if bundle.status != "approved":
        raise BundleWorkflowError(
            f"activate() requires bundle.status == 'approved', got {bundle.status!r}"
        )

    # Supersede any currently-active bundle for this tenant FIRST so the
    # partial UNIQUE index does not see two actives at flush time.
    stmt = select(PolicyBundleRow).where(
        PolicyBundleRow.tenant_id == bundle.tenant_id,
        PolicyBundleRow.status == "active",
    )
    result = await session.execute(stmt)
    prior_active = result.scalar_one_or_none()
    if prior_active is not None:
        await _write_approval(
            session,
            bundle=prior_active,
            from_status="active",
            to_status="superseded",
            actor_id=activator_actor_id,
            actor_role="system",
            reason=f"automatically superseded by activation of bundle {bundle_id}",
        )
        prior_active.status = "superseded"
        await session.flush()

    return await _transition(
        session,
        bundle_id=bundle_id,
        target_status="active",
        actor_id=activator_actor_id,
        reason=reason,
    )


async def supersede(
    session: AsyncSession,
    *,
    bundle_id: UUID,
    actor_id: UUID,
    reason: str,
) -> UUID:
    """Manually supersede an active bundle without activating a replacement.

    Used when a tenant wants to revoke their active bundle (e.g. a security
    incident) without immediately replacing it. After this call the tenant
    has no active bundle and ingest falls back to the bundle provider's
    cache-miss bootstrap path.
    """
    return await _transition(
        session,
        bundle_id=bundle_id,
        target_status="superseded",
        actor_id=actor_id,
        reason=reason,
    )


async def list_approvals_for_bundle(
    session: AsyncSession,
    bundle_id: UUID,
) -> list[PolicyBundleApprovalRow]:
    """Return all approval rows for a bundle, chronological (oldest first).

    For the future audit UI and for regulators inspecting the full history
    of a single bundle's approval lifecycle.
    """
    stmt = (
        select(PolicyBundleApprovalRow)
        .where(PolicyBundleApprovalRow.bundle_id == bundle_id)
        .order_by(PolicyBundleApprovalRow.decided_at.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


async def _load_bundle(session: AsyncSession, bundle_id: UUID) -> PolicyBundleRow:
    stmt = select(PolicyBundleRow).where(PolicyBundleRow.id == bundle_id).limit(1)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise BundleNotFoundError(f"bundle {bundle_id} not found")
    return row


async def _transition(
    session: AsyncSession,
    *,
    bundle_id: UUID,
    target_status: str,
    actor_id: UUID,
    reason: str,
) -> UUID:
    """Validate + execute a single forward transition. Pure state-machine logic."""
    if not reason or not reason.strip():
        raise BundleWorkflowError("reason is required and must be non-empty")

    bundle = await _load_bundle(session, bundle_id)
    current = bundle.status
    if target_status not in _VALID_TRANSITIONS.get(current, frozenset()):
        raise BundleWorkflowError(f"invalid transition {current!r} -> {target_status!r}")

    approval_id = await _write_approval(
        session,
        bundle=bundle,
        from_status=current,
        to_status=target_status,
        actor_id=actor_id,
        actor_role=_REQUIRED_ROLE[target_status],
        reason=reason,
    )
    bundle.status = target_status
    await session.flush()
    return approval_id


async def _write_approval(
    session: AsyncSession,
    *,
    bundle: PolicyBundleRow,
    from_status: str,
    to_status: str,
    actor_id: UUID | None,
    actor_role: str,
    reason: str,
) -> UUID:
    """Stage an approval row insert; caller's session_scope commits."""
    approval = PolicyBundleApprovalRow(
        id=uuid4(),
        bundle_id=bundle.id,
        tenant_id=bundle.tenant_id,
        from_status=from_status,
        to_status=to_status,
        actor_id=actor_id,
        actor_role=actor_role,
        reason=reason,
        decided_at=datetime.now(UTC),
    )
    session.add(approval)
    await session.flush()
    return approval.id

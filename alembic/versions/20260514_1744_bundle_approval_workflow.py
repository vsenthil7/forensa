"""add_bundle_approval_workflow

Revision ID: 0004_bundle_approval_workflow
Revises: 0003_event_output
Create Date: 2026-05-14 17:44:00 UTC

CP9.15 / NEW-P9.8.X.bundle-approval-workflow: adds the multi-step bundle
change-management workflow surfaced by the EnterpriseGradeReview 3.16
finding ("Bundle creation is a single function call. Enterprise needs
change-management: proposed -> reviewed -> approved -> activated, with
each step audit-logged").

This migration:

1. Adds a ``status`` column to ``policy_bundles`` with a CHECK constraint
   restricting it to the 5 allowed values. Existing rows (created before
   this migration) default to ``'proposed'`` so they are NOT silently
   treated as active - enterprise auditors should not see a bundle marked
   active without an approval row to back it. The CP9.14
   ``DefaultBundleProvider`` / ``PostgresBundleProvider`` cache-miss
   bootstrap path is unaffected because it persists fresh bundles which
   are then walked through the workflow by the calling code.

2. Adds a partial UNIQUE index ``uq_policy_bundles_one_active_per_tenant``
   on ``(tenant_id) WHERE status = 'active'``. Enforces the invariant
   "at most one active bundle per tenant" at the DB level so concurrent
   activations race-safely (one wins, the other gets IntegrityError).

3. Creates ``policy_bundle_approvals`` table: append-only audit log, one
   row per state transition. CHECK constraints on ``from_status``,
   ``to_status``, ``actor_role``. Indexes on ``(bundle_id, decided_at)``
   and ``(tenant_id, decided_at)`` for the audit UI.

Backwards-compatible: existing bundles continue to exist but in
``proposed`` status. ``get_active_bundle_for_tenant`` already filters on
``status='active'`` (updated in this CP) so it returns ``None`` for the
pre-migration data, which triggers the bundle-provider's cache-miss
bootstrap path. Net effect: the demo flow continues to work; only the
production wiring sees the new state machine.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004_bundle_approval_workflow"
down_revision: str | None = "0003_event_output"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add status column to policy_bundles with default 'proposed' for
    # existing rows. Then add CHECK + partial UNIQUE index.
    op.add_column(
        "policy_bundles",
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'proposed'"),
        ),
    )
    op.create_check_constraint(
        "ck_policy_bundles_status",
        "policy_bundles",
        "status IN ('proposed', 'reviewed', 'approved', 'active', 'superseded')",
    )
    op.create_index(
        "uq_policy_bundles_one_active_per_tenant",
        "policy_bundles",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    # 2. Create policy_bundle_approvals table.
    op.create_table(
        "policy_bundle_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("bundle_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_status", sa.String(length=16), nullable=False),
        sa.Column("to_status", sa.String(length=16), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_role", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=512), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bundle_id"], ["policy_bundles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "from_status IN ('proposed', 'reviewed', 'approved', 'active', 'superseded')",
            name="ck_policy_bundle_approvals_from_status",
        ),
        sa.CheckConstraint(
            "to_status IN ('proposed', 'reviewed', 'approved', 'active', 'superseded')",
            name="ck_policy_bundle_approvals_to_status",
        ),
        sa.CheckConstraint(
            "actor_role IN ('author', 'reviewer', 'approver', 'activator', 'system')",
            name="ck_policy_bundle_approvals_actor_role",
        ),
    )
    op.create_index(
        "ix_policy_bundle_approvals_bundle_decided",
        "policy_bundle_approvals",
        ["bundle_id", "decided_at"],
    )
    op.create_index(
        "ix_policy_bundle_approvals_tenant_decided",
        "policy_bundle_approvals",
        ["tenant_id", "decided_at"],
    )

    # 3. CP9.15.1: append-only enforcement at the DB level. The application
    # only ever INSERTs into policy_bundle_approvals, but defence-in-depth
    # requires the DB itself to refuse UPDATE/DELETE so a compromised
    # application connection cannot rewrite history. Implemented as a
    # PL/pgSQL trigger that raises on any non-INSERT mutation. Same
    # treatment applied to policy_bundles for the approval-bearing rows
    # would require row-level discrimination (active rows must still be
    # mutable to status='superseded'); for that table we rely on the
    # CHECK + partial UNIQUE constraints instead.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION forensa_block_approval_mutation()
        RETURNS TRIGGER LANGUAGE plpgsql AS $func$
        BEGIN
            RAISE EXCEPTION 'policy_bundle_approvals is append-only; % is forbidden', TG_OP;
        END;
        $func$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_policy_bundle_approvals_block_update
        BEFORE UPDATE ON policy_bundle_approvals
        FOR EACH ROW EXECUTE FUNCTION forensa_block_approval_mutation();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_policy_bundle_approvals_block_delete
        BEFORE DELETE ON policy_bundle_approvals
        FOR EACH ROW EXECUTE FUNCTION forensa_block_approval_mutation();
        """
    )

    # Drop the server_default after backfill so new INSERTs from Python
    # supply the value explicitly (matches the SQLAlchemy default on the
    # ORM column).
    op.alter_column("policy_bundles", "status", server_default=None)


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_policy_bundle_approvals_block_delete ON policy_bundle_approvals"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_policy_bundle_approvals_block_update ON policy_bundle_approvals"
    )
    op.execute("DROP FUNCTION IF EXISTS forensa_block_approval_mutation()")
    op.drop_index(
        "ix_policy_bundle_approvals_tenant_decided",
        table_name="policy_bundle_approvals",
    )
    op.drop_index(
        "ix_policy_bundle_approvals_bundle_decided",
        table_name="policy_bundle_approvals",
    )
    op.drop_table("policy_bundle_approvals")
    op.drop_index(
        "uq_policy_bundles_one_active_per_tenant",
        table_name="policy_bundles",
    )
    op.drop_constraint(
        "ck_policy_bundles_status",
        "policy_bundles",
        type_="check",
    )
    op.drop_column("policy_bundles", "status")

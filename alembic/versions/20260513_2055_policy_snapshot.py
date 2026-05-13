"""add_policy_snapshots

Revision ID: 0002_policy_snapshot
Revises: 0001_initial
Create Date: 2026-05-13 20:55:00 UTC

Adds the policy_snapshots table for BR-04 ingest-time policy binding, and
the receipts.policy_snapshot_id FK so every Receipt links to the exact
policy state active when its event was ingested.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002_policy_snapshot"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "policy_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_bundle_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_bundle_version", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verdict_decision", sa.String(length=16), nullable=False),
        sa.Column("verdict_reason", sa.String(length=512), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["policy_bundle_id"], ["policy_bundles.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "verdict_decision IN ('allow', 'deny', 'escalate')",
            name="ck_policy_snapshots_decision",
        ),
    )
    op.create_index("ix_policy_snapshots_bundle", "policy_snapshots", ["policy_bundle_id"])
    op.create_index(
        "ix_policy_snapshots_tenant_captured",
        "policy_snapshots",
        ["tenant_id", "captured_at"],
    )
    op.create_index("ix_policy_snapshots_content_hash", "policy_snapshots", ["content_hash"])

    op.add_column(
        "receipts",
        sa.Column(
            "policy_snapshot_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_receipts_policy_snapshot",
        "receipts",
        "policy_snapshots",
        ["policy_snapshot_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_receipts_policy_snapshot", "receipts", ["policy_snapshot_id"])


def downgrade() -> None:
    op.drop_index("ix_receipts_policy_snapshot", table_name="receipts")
    op.drop_constraint("fk_receipts_policy_snapshot", "receipts", type_="foreignkey")
    op.drop_column("receipts", "policy_snapshot_id")
    op.drop_index("ix_policy_snapshots_content_hash", table_name="policy_snapshots")
    op.drop_index("ix_policy_snapshots_tenant_captured", table_name="policy_snapshots")
    op.drop_index("ix_policy_snapshots_bundle", table_name="policy_snapshots")
    op.drop_table("policy_snapshots")

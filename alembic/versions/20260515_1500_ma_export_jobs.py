"""add_ma_export_jobs

Revision ID: 0008_ma_export_jobs
Revises: 0007_timestamp_anchors
Create Date: 2026-05-15 15:00:00 UTC

CP9.43 / IP #8 NEW-P12.X.ma-export-async-job (schema half).

For very large M&A export windows (12+ months, 50K+ receipts) the
synchronous POST /v1/exports/ma-diligence route hits HTTP timeouts.
This migration creates the ``ma_export_jobs`` table that backs the
async-job variant:

  POST /v1/exports/ma-diligence/jobs       -> 202 Accepted + job_id
  GET  /v1/exports/ma-diligence/jobs/{id}  -> status + result_export

The row tracks the job through a forward-only state machine:

    pending -> running -> completed
                      \\-> failed
    pending -> failed   (startup failure before work begins)

Schema design notes
-------------------

- ``status`` CHECK constraint enforces the enum at DB level. Application
  layer additionally enforces forward-only transitions (CP9.44).
- ``result_export`` is JSONB so MaDiligenceExport (or a CipherEnvelope
  wrapping it) lands intact. The GET-by-id route reads it back without
  re-running the export.
- ``result_error`` is bounded to 2048 chars so a runaway exception
  traceback can't fill the row.
- ``requested_by_agent_id`` is NULLable for jobs scheduled by system
  processes (future: maintenance / scheduled exports).
- ``encrypt_for_pubkey_b64`` + ``platform_sign_key_id`` snapshot the
  encryption/signing options from the original POST so the worker has
  everything it needs without joining other tables.
- Two indexes:
    ix_ma_export_jobs_tenant_requested: list jobs for a tenant in
      reverse-chronological order (the dashboard view).
    ix_ma_export_jobs_status: worker poll path "give me one pending
      job to claim".

Reversibility
-------------

Downgrade drops the table cleanly. No dependent objects elsewhere
reference ma_export_jobs.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_ma_export_jobs"
down_revision: str | None = "0007_timestamp_anchors"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ma_export_jobs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "requested_by_agent_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="RESTRICT"),
            nullable=True,
            comment=(
                "Agent under which the job was POSTed (for audit). Nullable"
                " for jobs scheduled by system processes."
            ),
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("scope_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scope_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "encrypt_for_pubkey_b64",
            sa.String(64),
            nullable=True,
            comment=(
                "Optional acquirer X25519 pubkey (base64). When set, the"
                " worker encrypts the result before writing it to"
                " result_export."
            ),
        ),
        sa.Column(
            "platform_sign_key_id",
            sa.String(128),
            nullable=True,
            comment=(
                "Optional Forensa platform key id (CP9.34). When set, the"
                " worker platform-signs the export before writing to"
                " result_export."
            ),
        ),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "result_export",
            sa.dialects.postgresql.JSONB,
            nullable=True,
            comment=(
                "MaDiligenceExport JSON (or CipherEnvelope wrapping it when"
                " encrypt_for_pubkey_b64 was set). Populated iff"
                " status='completed'."
            ),
        ),
        sa.Column(
            "result_error",
            sa.String(2048),
            nullable=True,
            comment=(
                "Error message. Populated iff status='failed'. Bounded to"
                " 2048 chars so a runaway traceback can't fill the row."
            ),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_ma_export_jobs_status",
        ),
    )
    op.create_index(
        "ix_ma_export_jobs_tenant_requested",
        "ma_export_jobs",
        ["tenant_id", "requested_at"],
    )
    op.create_index(
        "ix_ma_export_jobs_status",
        "ma_export_jobs",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_ma_export_jobs_status", table_name="ma_export_jobs")
    op.drop_index("ix_ma_export_jobs_tenant_requested", table_name="ma_export_jobs")
    op.drop_table("ma_export_jobs")

"""add_timestamp_anchors

Revision ID: 0007_timestamp_anchors
Revises: 0006_agent_signature
Create Date: 2026-05-15 00:18:00 UTC

CP9.19 / BR-06 (RFC 3161 TSA anchoring): closes the Enterprise-Grade
Review section 3.10 finding "No TSA (RFC 3161) timestamp anchor. BR-06
says Merkle-chained ledger with RFC 3161 TSA. Today signed_at is a
server-clock value from datetime.now(UTC). A regulator with T+1 year
doubt cannot prove the server clock wasn't set wrong."

This migration creates the ``timestamp_anchors`` table:

- One row per ``(tenant_id, anchor_date)``.
- ``root_hash``: the latest receipt_hash for the tenant on that date.
  Any earlier receipt that day is provably included via the hash chain.
- ``tsr_bytes`` + ``tsa_signature`` + ``timestamped_at``: the TSA's
  signed response, persisted intact for regulator replay.
- ``status``: 'anchored' (TSA returned valid response) or 'deferred'
  (TSA unavailable / no receipts to anchor). Deferred rows are tombstones
  retried by the next anchor run.

Append-only by design. Reprocessing a deferred row updates IS NOT a SQL
UPDATE - the application layer instead INSERTs a new row with the same
``(tenant_id, anchor_date)`` only after the previous row was marked
'deferred', then deletes the deferred tombstone via a transactional
swap. This keeps the ``uq_timestamp_anchors_tenant_date`` UNIQUE
constraint useful as a write-once guard for successful anchors.

CHECK constraint enforces the status enum at DB level.

Reversibility: downgrade drops the table and its constraints cleanly. No
dependent objects elsewhere reference timestamp_anchors (receipts are
NOT modified; the anchor table is a separate witness layer).

Why we don't store the TSA's public key on the row
---------------------------------------------------

The TSA's public key (or certificate chain in real RFC 3161) is the
trust anchor, not per-anchor data. It belongs in tenant config or in a
shared TSA registry table - tracked as NEW-P9.19.tsa-public-key-registry
and landed in CP10.x. Today the verifier resolves the public key by
``tsa_identifier`` via an in-process mapping for the hackathon demo.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_timestamp_anchors"
down_revision: str | None = "0006_agent_signature"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "timestamp_anchors",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "anchor_date",
            sa.DateTime(timezone=True),
            nullable=False,
            comment=(
                "Calendar date (UTC midnight) this anchor covers. Used as the"
                " coarse grouping key alongside tenant_id."
            ),
        ),
        sa.Column(
            "root_hash",
            sa.String(64),
            nullable=True,
            comment=(
                "Latest receipt_hash for this tenant on anchor_date. NULL iff" " status='deferred'."
            ),
        ),
        sa.Column("tsa_identifier", sa.String(256), nullable=False),
        sa.Column(
            "tsr_bytes",
            sa.LargeBinary,
            nullable=True,
            comment=(
                "Raw TSR from TSA. NULL iff status='deferred'. Production:"
                " ASN.1 DER per RFC 3161. Mock: deterministic JSON."
            ),
        ),
        sa.Column(
            "tsa_signature",
            sa.LargeBinary(length=64),
            nullable=True,
            comment="Ed25519 sig from TSA. NULL iff status='deferred'.",
        ),
        sa.Column(
            "timestamped_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment=(
                "When the TSA claims the root was witnessed (their clock)."
                " NULL iff status='deferred'."
            ),
        ),
        sa.Column(
            "anchored_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When Forensa persisted this anchor row (server clock).",
        ),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            comment=(
                "'anchored' = TSA returned a valid response; 'deferred' = TSA"
                " was unavailable or no receipts to anchor."
            ),
        ),
        sa.UniqueConstraint("tenant_id", "anchor_date", name="uq_timestamp_anchors_tenant_date"),
        sa.CheckConstraint(
            "status IN ('anchored', 'deferred')",
            name="ck_timestamp_anchors_status",
        ),
    )
    op.create_index(
        "ix_timestamp_anchors_tenant_anchored",
        "timestamp_anchors",
        ["tenant_id", "anchored_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_timestamp_anchors_tenant_anchored", table_name="timestamp_anchors")
    op.drop_table("timestamp_anchors")

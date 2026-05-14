"""add_event_output_field

Revision ID: 0003_event_output
Revises: 0002_policy_snapshot
Create Date: 2026-05-14 15:25:00 UTC

CP9.9 / NEW-P9.8.21: adds the ``events.output`` column, separating the
model's response text from the agent's reasoning. Prior to this migration,
``packages/ingest/normaliser.py`` was capturing ``gen_ai.response.text``
(model output) as ``reasoning`` (agent rationale). They are semantically
different things and the conflation would mislead investigators.

Backwards-compatible: nullable column with NULL default. Old events
ingested under the buggy normaliser still have their (incorrectly-labelled)
data in ``reasoning``; manual migration of those rows is OUT OF SCOPE for
this revision because v1 has not yet ingested customer data.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_event_output"
down_revision: str | None = "0002_policy_snapshot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column("output", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("events", "output")

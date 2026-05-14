"""add_idempotency_records

Revision ID: 0005_idempotency_records
Revises: 0004_bundle_approval_workflow
Create Date: 2026-05-14 21:20:00 UTC

CP9.17 / NEW-P9.8.2: adds the request-deduplication table backing
``PostgresIdempotencyStore``. Stripe-style Idempotency-Key contract on
mutating routes (today: POST /v1/events; future: any other write route).

Table shape:

- ``(tenant_id, key)`` composite primary key. Tenant binding is explicit so
  the same Idempotency-Key from two different tenants is two separate
  records (no cross-tenant key collision possible).
- ``body_hash``: SHA-256 hex of the canonical-JSON request body. Same key
  + same body within the TTL window -> return cached response. Same key
  + different body -> 409 Conflict.
- ``response_status`` and ``response_body``: the original 201 (or other
  successful 2xx) the client received. JSONB for response_body so we can
  query into it forensically without parsing.
- ``stored_at`` and ``expires_at`` (both timezone-aware): TTL window.
  Default TTL is 24h, set by application code via
  ``InMemoryIdempotencyStore._default_ttl``. ``lookup_or_claim`` filters
  on ``expires_at > now()`` so expired records are tombstones, not bugs.
- Index on ``expires_at`` so the future cleanup cron
  (``NEW-P9.17.1.idempotency-store-cleanup-job``) can range-scan stale
  rows efficiently without touching the composite primary key index.

Deliberately decoupled from the Receipt chain:

- ``tenant_id`` is NOT an FK to ``tenants(id)``. Idempotency records are
  a request dedup cache, not part of the audit ledger. Coupling them to
  the tenant lifecycle would mean a tenant deletion would CASCADE through
  the cache (or RESTRICT and block tenant deletion), neither of which is
  desirable for a transient dedup table.
- No ondelete RESTRICT FK forest around it. The append-only triggers
  installed on ``policy_bundle_approvals`` are NOT installed here -
  expired idempotency records SHOULD be deletable by the cleanup cron.

Reversibility: ``downgrade`` drops the table cleanly. No dependent objects
elsewhere reference it.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005_idempotency_records"
down_revision: str | None = "0004_bundle_approval_workflow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "idempotency_records",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("body_hash", sa.String(length=64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", postgresql.JSONB(), nullable=False),
        sa.Column("stored_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id", "key", name="pk_idempotency_records"),
        sa.CheckConstraint(
            "char_length(key) >= 16 AND char_length(key) <= 128",
            name="ck_idempotency_records_key_length",
        ),
        sa.CheckConstraint(
            "char_length(body_hash) = 64",
            name="ck_idempotency_records_body_hash_length",
        ),
        sa.CheckConstraint(
            "response_status >= 200 AND response_status < 600",
            name="ck_idempotency_records_response_status_range",
        ),
        sa.CheckConstraint(
            "expires_at > stored_at",
            name="ck_idempotency_records_expires_after_stored",
        ),
    )
    op.create_index(
        "ix_idempotency_records_expires_at",
        "idempotency_records",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_idempotency_records_expires_at",
        table_name="idempotency_records",
    )
    op.drop_table("idempotency_records")

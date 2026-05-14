"""add_agent_signature

Revision ID: 0006_agent_signature
Revises: 0005_idempotency_records
Create Date: 2026-05-14 22:30:00 UTC

CP9.18 / BR-02 (Multi-party identity binding): closes the
Enterprise-Grade Review section 3.10 finding "No agent signature path.
BR-02 (dual signature) is unmet. Today only the tenant signs. Adding a
second signature requires another field, another verifier, another KMS
adapter."

This migration adds a single ``agent_signature`` column to ``receipts``:

- 64-byte LargeBinary, NULLable.
- NULLable because receipts persisted before this migration won't have an
  agent signature; we deliberately do NOT backfill (we can't - we don't
  have the agent's private key to retroactively sign old hashes, and even
  if we did, retroactive signing would defeat the audit purpose).
- All Receipts created on or after CP9.18 MUST populate this column at
  application-layer (enforced in ``packages/ledger/receipt_builder.py``).
- Two independent Ed25519 signatures over the same ``receipt_hash``:
  tenant signature (existing ``signature`` column) and agent signature
  (this new column). Each verifies independently with its respective
  public key.

CHECK constraint enforces the column length at DB level so any future raw
SQL INSERT cannot land a malformed 32-byte or 96-byte signature.

Reversibility: downgrade drops the column cleanly. No dependent objects
elsewhere reference it (downstream evidence packs serialise the column
optionally via JSON; absence at the column layer becomes ``null`` in the
pack JSON-LD).

Why this is not retro-applicable to old receipts
-------------------------------------------------

A receipt's ``receipt_hash`` was bound at the moment of signing, using the
fields in ``packages.ledger.receipt_builder._compute_receipt_hash``. The
agent_signature signs that same hash. We could, in principle, generate
agent keypairs today and sign every historical receipt_hash - but those
signatures would assert "the agent identified at THIS_NEW_KEY witnessed
this hash AT MIGRATION TIME", which is meaningless. The whole point of a
multi-party signature is contemporaneous witness; retroactive signature
is a different (and weaker) artifact. We let old receipts remain
single-signature and mark them as such in the audit UI.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_agent_signature"
down_revision: str | None = "0005_idempotency_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "receipts",
        sa.Column(
            "agent_signature",
            sa.LargeBinary(length=64),
            nullable=True,
            comment=(
                "Ed25519 signature over receipt_hash by the agent's key "
                "(CP9.18 / BR-02 dual-signature). NULL for pre-CP9.18 receipts."
            ),
        ),
    )
    op.create_check_constraint(
        "ck_receipts_agent_signature_length",
        "receipts",
        "agent_signature IS NULL OR octet_length(agent_signature) = 64",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_receipts_agent_signature_length",
        "receipts",
        type_="check",
    )
    op.drop_column("receipts", "agent_signature")

"""initial_schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-13 09:30:00 UTC

Creates the Forensa evidence ledger: 5 append-only tables with FKs,
indexes, and CHECK/UNIQUE constraints matching packages.ledger.models.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tenants',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('slug', sa.String(length=63), nullable=False),
        sa.Column('display_name', sa.String(length=200), nullable=False),
        sa.Column('signing_key_id', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('slug', name='uq_tenants_slug'),
    )
    op.create_index('ix_tenants_slug', 'tenants', ['slug'], unique=True)

    op.create_table(
        'agents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('slug', sa.String(length=63), nullable=False),
        sa.Column('display_name', sa.String(length=200), nullable=False),
        sa.Column('identity_public_key', sa.LargeBinary(length=32), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False, server_default=sa.text("'active'")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('tenant_id', 'slug', name='uq_agents_tenant_slug'),
        sa.CheckConstraint("status IN ('active', 'suspended', 'retired')", name='ck_agents_status'),
    )
    op.create_index('ix_agents_tenant_id', 'agents', ['tenant_id'])

    op.create_table(
        'policy_bundles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version', sa.String(length=64), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('content', postgresql.JSONB, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('tenant_id', 'version', name='uq_policy_bundles_tenant_version'),
    )
    op.create_index('ix_policy_bundles_tenant_id', 'policy_bundles', ['tenant_id'])
    op.create_index('ix_policy_bundles_content_hash', 'policy_bundles', ['content_hash'])

    op.create_table(
        'events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('trace_id', sa.String(length=32), nullable=False),
        sa.Column('span_id', sa.String(length=16), nullable=False),
        sa.Column('parent_span_id', sa.String(length=16), nullable=True),
        sa.Column('kind', sa.String(length=32), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('payload', postgresql.JSONB, nullable=False),
        sa.Column('reasoning', sa.String(), nullable=True),
        sa.Column('policy_version', sa.String(length=64), nullable=True),
        sa.Column('policy_verdict', sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='RESTRICT'),
    )
    op.create_index('ix_events_trace_span', 'events', ['trace_id', 'span_id'])
    op.create_index('ix_events_tenant_occurred', 'events', ['tenant_id', 'occurred_at'])

    op.create_table(
        'receipts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('policy_bundle_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sequence', sa.BigInteger(), nullable=False),
        sa.Column('prev_receipt_hash', sa.String(length=64), nullable=True),
        sa.Column('payload_hash', sa.String(length=64), nullable=False),
        sa.Column('receipt_hash', sa.String(length=64), nullable=False),
        sa.Column('signature', sa.LargeBinary(length=64), nullable=False),
        sa.Column('signed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['policy_bundle_id'], ['policy_bundles.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('tenant_id', 'sequence', name='uq_receipts_tenant_sequence'),
        sa.UniqueConstraint('receipt_hash', name='uq_receipts_receipt_hash'),
        sa.CheckConstraint('sequence >= 0', name='ck_receipts_sequence_nonneg'),
    )
    op.create_index('ix_receipts_event', 'receipts', ['event_id'])
    op.create_index('ix_receipts_tenant_signed', 'receipts', ['tenant_id', 'signed_at'])


def downgrade() -> None:
    op.drop_table('receipts')
    op.drop_table('events')
    op.drop_table('policy_bundles')
    op.drop_table('agents')
    op.drop_table('tenants')


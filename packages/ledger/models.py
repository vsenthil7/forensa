"""SQLAlchemy 2.0 async ORM models for the Forensa evidence ledger.

Mirrors the Pydantic schemas in packages.schema. Append-only by design:
no UPDATE or DELETE statements should ever target receipts or events.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all Forensa ORM models."""


class TenantRow(Base):
    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    slug: Mapped[str] = mapped_column(String(63), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    signing_key_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    agents: Mapped[list["AgentRow"]] = relationship(back_populates="tenant")


class AgentRow(Base):
    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_agents_tenant_slug"),
        CheckConstraint(
            "status IN ('active', 'suspended', 'retired')",
            name="ck_agents_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    slug: Mapped[str] = mapped_column(String(63), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    identity_public_key: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    tenant: Mapped[TenantRow] = relationship(back_populates="agents")


class PolicyBundleRow(Base):
    __tablename__ = "policy_bundles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "version", name="uq_policy_bundles_tenant_version"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EventRow(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_trace_span", "trace_id", "span_id"),
        Index("ix_events_tenant_occurred", "tenant_id", "occurred_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    trace_id: Mapped[str] = mapped_column(String(32), nullable=False)
    span_id: Mapped[str] = mapped_column(String(16), nullable=False)
    parent_span_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    reasoning: Mapped[str | None] = mapped_column(String, nullable=True)
    policy_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    policy_verdict: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ReceiptRow(Base):
    __tablename__ = "receipts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sequence", name="uq_receipts_tenant_sequence"),
        Index("ix_receipts_event", "event_id"),
        Index("ix_receipts_tenant_signed", "tenant_id", "signed_at"),
        CheckConstraint("sequence >= 0", name="ck_receipts_sequence_nonneg"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("events.id", ondelete="RESTRICT"),
        nullable=False,
    )
    policy_bundle_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("policy_bundles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    prev_receipt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    receipt_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    signature: Mapped[bytes] = mapped_column(LargeBinary(64), nullable=False)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

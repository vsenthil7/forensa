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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
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

    agents: Mapped[list[AgentRow]] = relationship(back_populates="tenant")


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
    """Policy bundle ORM row.

    The ``status`` column (added in alembic 0004 / CP9.15) tracks the bundle's
    position in the approval workflow:

    - ``proposed`` -> just authored, no review yet
    - ``reviewed`` -> a reviewer (separate from author) signed off
    - ``approved`` -> an approver (separate from reviewer) signed off
    - ``active``   -> currently in use for ingest. At most ONE per tenant
      (enforced by ``uq_policy_bundles_one_active_per_tenant`` partial unique
      index).
    - ``superseded`` -> formerly active, replaced by a newer bundle.

    Forward-only transitions only - see ``packages.ledger.bundle_workflow``.
    Bundles persisted before alembic 0004 default to ``proposed`` so they are
    NOT silently treated as active (intentional: enterprise auditors should
    not see a bundle marked active without an approval row to back it).
    """

    __tablename__ = "policy_bundles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "version", name="uq_policy_bundles_tenant_version"),
        CheckConstraint(
            "status IN ('proposed', 'reviewed', 'approved', 'active', 'superseded')",
            name="ck_policy_bundles_status",
        ),
        Index(
            "uq_policy_bundles_one_active_per_tenant",
            "tenant_id",
            unique=True,
            postgresql_where="status = 'active'",
        ),
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
    # CP9.15 / NEW-P9.8.X.bundle-approval-workflow. Default proposed at write
    # time; only the workflow module mutates this column.
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="proposed")


class PolicyBundleApprovalRow(Base):
    """One row per state transition in the bundle approval workflow.

    Append-only audit log: every transition (``from_status`` -> ``to_status``)
    produces a new row. Captures actor identity, role, reason, and timestamp.
    A future CP wires each row to also emit a Forensa Receipt (eat your own
    dogfood) - tracked as ``NEW-P9.15.bundle-approval-receipts``.

    Actor identity is opaque today (``actor_id`` is just a UUID, ``actor_role``
    is a free-form short string) because per-step auth lands in CP10.x. The
    column exists now so future auth can fill it without a migration.
    """

    __tablename__ = "policy_bundle_approvals"
    __table_args__ = (
        CheckConstraint(
            "from_status IN ('proposed', 'reviewed', 'approved', 'active', 'superseded')",
            name="ck_policy_bundle_approvals_from_status",
        ),
        CheckConstraint(
            "to_status IN ('proposed', 'reviewed', 'approved', 'active', 'superseded')",
            name="ck_policy_bundle_approvals_to_status",
        ),
        CheckConstraint(
            "actor_role IN ('author', 'reviewer', 'approver', 'activator', 'system')",
            name="ck_policy_bundle_approvals_actor_role",
        ),
        Index(
            "ix_policy_bundle_approvals_bundle_decided",
            "bundle_id",
            "decided_at",
        ),
        Index(
            "ix_policy_bundle_approvals_tenant_decided",
            "tenant_id",
            "decided_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    bundle_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("policy_bundles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    from_status: Mapped[str] = mapped_column(String(16), nullable=False)
    to_status: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    actor_role: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(String(512), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PolicySnapshotRow(Base):
    """BR-04: ingest-time bind of (policy bundle state, verdict produced).

    Captures the exact policy_bundle.content_hash that was active when an event
    was ingested, even if the bundle itself is later replaced or rebuilt. Every
    Receipt links to a PolicySnapshot via FK so replay can use the snapshot's
    content_hash rather than whatever the live bundle currently shows.
    """

    __tablename__ = "policy_snapshots"
    __table_args__ = (
        CheckConstraint(
            "verdict_decision IN ('allow', 'deny', 'escalate')",
            name="ck_policy_snapshots_decision",
        ),
        Index("ix_policy_snapshots_bundle", "policy_bundle_id"),
        Index("ix_policy_snapshots_tenant_captured", "tenant_id", "captured_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    policy_bundle_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("policy_bundles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    policy_bundle_version: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verdict_decision: Mapped[str] = mapped_column(String(16), nullable=False)
    verdict_reason: Mapped[str] = mapped_column(String(512), nullable=False)


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
    output: Mapped[str | None] = mapped_column(String, nullable=True)
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
    policy_snapshot_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("policy_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    prev_receipt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    receipt_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    signature: Mapped[bytes] = mapped_column(LargeBinary(64), nullable=False)
    agent_signature: Mapped[bytes | None] = mapped_column(
        LargeBinary(64),
        nullable=True,
        comment=(
            "CP9.18 / BR-02 dual signature. Ed25519 over receipt_hash by the"
            " agent's key (independent witness from the tenant's signature)."
            " NULLable for backwards compat with receipts persisted before"
            " alembic 0006; new ingest paths MUST populate it."
        ),
    )
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TimestampAnchorRow(Base):
    """CP9.19 / BR-06: external-TSA anchor of a tenant's receipt chain on a date.

    One row per ``(tenant_id, anchor_date)`` covers ALL receipts for that
    tenant on that date. The anchor's ``root_hash`` is the ``receipt_hash``
    of the latest receipt for the tenant whose ``signed_at`` falls within
    ``[anchor_date 00:00:00 UTC, anchor_date 23:59:59.999999 UTC]``. Any
    earlier receipt that day is provably included because the chain is
    hash-linked.

    The ``tsr_bytes`` column holds the raw TSR returned by the TSA
    (production: ASN.1 DER per RFC 3161 §3.5; mock: deterministic JSON).
    A regulator with the TSA's public key can verify ``tsa_signature``
    against ``(root_hash, timestamped_at)`` and prove the root existed
    at the timestamp.

    Append-only by design. Reprocessing a day's chain (e.g. because the
    TSA was down on the original date) writes a NEW row with the same
    ``(tenant_id, anchor_date)`` only if the previous row's
    ``status='deferred'`` (a tombstone) - enforced at the application
    layer via the anchor module.
    """

    __tablename__ = "timestamp_anchors"
    __table_args__ = (
        UniqueConstraint("tenant_id", "anchor_date", name="uq_timestamp_anchors_tenant_date"),
        CheckConstraint(
            "status IN ('anchored', 'deferred')",
            name="ck_timestamp_anchors_status",
        ),
        Index("ix_timestamp_anchors_tenant_anchored", "tenant_id", "anchored_at"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    anchor_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment=(
            "Calendar date (UTC midnight) this anchor covers. Used as the"
            " coarse grouping key alongside tenant_id."
        ),
    )
    root_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment=(
            "Latest receipt_hash for this tenant on anchor_date. NULL iff"
            " status='deferred' (no receipts to anchor or TSA unavailable)."
        ),
    )
    tsa_identifier: Mapped[str] = mapped_column(String(256), nullable=False)
    tsr_bytes: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
        comment=(
            "Raw TSR from TSA. NULL iff status='deferred'. Production: ASN.1"
            " DER per RFC 3161. Mock: deterministic JSON."
        ),
    )
    tsa_signature: Mapped[bytes | None] = mapped_column(
        LargeBinary(64),
        nullable=True,
        comment="Ed25519 sig from TSA. NULL iff status='deferred'.",
    )
    timestamped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment=(
            "When the TSA claims the root was witnessed (their clock). NULL iff"
            " status='deferred'."
        ),
    )
    anchored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="When Forensa persisted this anchor row (server clock).",
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment=(
            "'anchored' = TSA returned a valid response; 'deferred' = TSA was"
            " unavailable or no receipts to anchor; anchor module retries"
            " deferred rows on the next run."
        ),
    )


class MaExportJobRow(Base):
    """CP9.43 / IP #8 NEW-P12.X.ma-export-async-job.

    Background-job tracking row for very large M&A export windows. When a
    caller POSTs to /v1/exports/ma-diligence/jobs, a new row is created
    with ``status='pending'``. A worker (today: an asyncio task scheduled
    on the request handler; future: a Celery / Arq / EventBridge worker)
    picks it up, transitions to ``running``, performs the export, and
    writes either ``status='completed'`` + ``result_export`` or
    ``status='failed'`` + ``result_error``.

    The bundle itself lives in ``result_export`` as the full serialised
    MaDiligenceExport JSON (or a CipherEnvelope JSON when encryption was
    requested) so the GET-by-id endpoint can return it without
    re-running the export.

    Append-only after the terminal state. Once status moves to
    ``completed`` or ``failed`` the row is immutable. The application
    layer enforces this; production should also add a database trigger.

    Status state machine (forward-only):
        pending -> running -> completed
                          \\-> failed
        pending -> failed  (a startup failure before work begins)

    Why not reuse PolicyBundleApprovalRow's pattern of one row per
    transition: M&A export status is a job's CURRENT state, not its
    audit history. Three status mutations per job vs ~20 per bundle
    workflow; the row-per-transition pattern would be over-engineered
    for this scale.
    """

    __tablename__ = "ma_export_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_ma_export_jobs_status",
        ),
        Index("ix_ma_export_jobs_tenant_requested", "tenant_id", "requested_at"),
        Index("ix_ma_export_jobs_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    requested_by_agent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="RESTRICT"),
        nullable=True,
        comment=(
            "Agent under which the job was POSTed (for audit). Nullable for"
            " jobs scheduled by system processes."
        ),
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")

    # Job parameters: snapshot of the original request so the row is
    # self-describing without joining other tables.
    scope_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scope_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    encrypt_for_pubkey_b64: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment=(
            "Optional acquirer X25519 pubkey (base64). When set, the worker"
            " encrypts the result before writing it to result_export."
        ),
    )
    platform_sign_key_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment=(
            "Optional Forensa platform key id (CP9.34). When set, the worker"
            " platform-signs the export before writing to result_export."
        ),
    )

    # Lifecycle timestamps.
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Outcome: exactly one of (result_export, result_error) is populated
    # once status is terminal. Both NULL while pending or running.
    result_export: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment=(
            "MaDiligenceExport JSON (or CipherEnvelope wrapping it when"
            " encrypt_for_pubkey_b64 was set). Populated iff status='completed'."
        ),
    )
    result_error: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
        comment=(
            "Error message. Populated iff status='failed'. Bounded to 2048"
            " chars so a runaway exception traceback can't fill the row."
        ),
    )

"""Tests for ledger ORM models — verifies metadata, columns, constraints, indexes."""

from __future__ import annotations

from sqlalchemy import inspect

from packages.ledger.models import (
    AgentRow,
    Base,
    EventRow,
    MaExportJobRow,
    PolicyBundleApprovalRow,
    PolicyBundleRow,
    PolicySnapshotRow,
    ReceiptRow,
    TenantRow,
    TimestampAnchorRow,
)


def test_all_tables_registered():
    names = {t.name for t in Base.metadata.tables.values()}
    assert names == {
        "tenants",
        "agents",
        "policy_bundles",
        "policy_bundle_approvals",  # CP9.15
        "policy_snapshots",
        "events",
        "receipts",
        "timestamp_anchors",  # CP9.19 - BR-06 RFC 3161 TSA anchoring
        "ma_export_jobs",  # CP9.43 - IP #8 async M&A export jobs
    }


def test_tenant_columns():
    cols = {c.name for c in TenantRow.__table__.columns}
    assert cols == {"id", "slug", "display_name", "signing_key_id", "created_at"}
    assert TenantRow.__table__.columns["slug"].unique is True


def test_agent_columns_and_fk():
    cols = {c.name for c in AgentRow.__table__.columns}
    assert cols == {
        "id",
        "tenant_id",
        "slug",
        "display_name",
        "identity_public_key",
        "status",
        "created_at",
    }
    fks = list(AgentRow.__table__.columns["tenant_id"].foreign_keys)
    assert len(fks) == 1
    assert fks[0].target_fullname == "tenants.id"
    constraint_names = {c.name for c in AgentRow.__table__.constraints if c.name}
    assert "uq_agents_tenant_slug" in constraint_names
    assert "ck_agents_status" in constraint_names


def test_policy_bundle_columns_and_uq():
    cols = {c.name for c in PolicyBundleRow.__table__.columns}
    assert cols == {
        "id",
        "tenant_id",
        "version",
        "content_hash",
        "content",
        "created_at",
        "status",  # CP9.15 - bundle approval workflow
    }
    constraint_names = {c.name for c in PolicyBundleRow.__table__.constraints if c.name}
    assert "uq_policy_bundles_tenant_version" in constraint_names
    assert "ck_policy_bundles_status" in constraint_names  # CP9.15
    idx_names = {ix.name for ix in PolicyBundleRow.__table__.indexes}
    assert "uq_policy_bundles_one_active_per_tenant" in idx_names  # CP9.15 partial UNIQUE


def test_policy_bundle_approval_columns_and_constraints():
    """CP9.15 / NEW-P9.8.X.bundle-approval-workflow: new policy_bundle_approvals table."""
    cols = {c.name for c in PolicyBundleApprovalRow.__table__.columns}
    assert cols == {
        "id",
        "bundle_id",
        "tenant_id",
        "from_status",
        "to_status",
        "actor_id",
        "actor_role",
        "reason",
        "decided_at",
    }
    constraint_names = {c.name for c in PolicyBundleApprovalRow.__table__.constraints if c.name}
    assert "ck_policy_bundle_approvals_from_status" in constraint_names
    assert "ck_policy_bundle_approvals_to_status" in constraint_names
    assert "ck_policy_bundle_approvals_actor_role" in constraint_names
    idx_names = {ix.name for ix in PolicyBundleApprovalRow.__table__.indexes}
    assert "ix_policy_bundle_approvals_bundle_decided" in idx_names
    assert "ix_policy_bundle_approvals_tenant_decided" in idx_names
    # FKs to policy_bundles and tenants
    fks = {fk.target_fullname for fk in PolicyBundleApprovalRow.__table__.foreign_keys}
    assert fks == {"policy_bundles.id", "tenants.id"}
    # actor_id is nullable (today's auth is opaque); actor_role is NOT nullable
    assert PolicyBundleApprovalRow.__table__.columns["actor_id"].nullable is True
    assert PolicyBundleApprovalRow.__table__.columns["actor_role"].nullable is False


def test_event_columns_and_indexes():
    cols = {c.name for c in EventRow.__table__.columns}
    assert cols == {
        "id",
        "tenant_id",
        "agent_id",
        "trace_id",
        "span_id",
        "parent_span_id",
        "kind",
        "occurred_at",
        "payload",
        "reasoning",
        "output",  # CP9.9 / NEW-P9.8.21 - separate from reasoning
        "policy_version",
        "policy_verdict",
    }
    idx_names = {ix.name for ix in EventRow.__table__.indexes}
    assert "ix_events_trace_span" in idx_names
    assert "ix_events_tenant_occurred" in idx_names
    fks = {fk.target_fullname for fk in EventRow.__table__.foreign_keys}
    assert "tenants.id" in fks
    assert "agents.id" in fks


def test_event_parent_span_id_is_nullable():
    assert EventRow.__table__.columns["parent_span_id"].nullable is True
    assert EventRow.__table__.columns["reasoning"].nullable is True
    assert EventRow.__table__.columns["output"].nullable is True  # CP9.9
    assert EventRow.__table__.columns["policy_version"].nullable is True
    assert EventRow.__table__.columns["policy_verdict"].nullable is True


def test_receipt_columns_and_constraints():
    cols = {c.name for c in ReceiptRow.__table__.columns}
    assert cols == {
        "id",
        "tenant_id",
        "event_id",
        "policy_bundle_id",
        "policy_snapshot_id",
        "sequence",
        "prev_receipt_hash",
        "payload_hash",
        "receipt_hash",
        "signature",
        "agent_signature",  # CP9.18 - BR-02 dual signature
        "signed_at",
    }
    constraint_names = {c.name for c in ReceiptRow.__table__.constraints if c.name}
    assert "uq_receipts_tenant_sequence" in constraint_names
    assert "ck_receipts_sequence_nonneg" in constraint_names
    idx_names = {ix.name for ix in ReceiptRow.__table__.indexes}
    assert "ix_receipts_event" in idx_names
    assert "ix_receipts_tenant_signed" in idx_names
    assert ReceiptRow.__table__.columns["receipt_hash"].unique is True
    assert ReceiptRow.__table__.columns["prev_receipt_hash"].nullable is True
    # CP9.18: agent_signature is nullable for backwards compat with
    # pre-migration-0006 receipts.
    assert ReceiptRow.__table__.columns["agent_signature"].nullable is True


def test_receipt_fks_to_events_and_policy_bundles():
    fks = {fk.target_fullname for fk in ReceiptRow.__table__.foreign_keys}
    assert fks == {
        "tenants.id",
        "events.id",
        "policy_bundles.id",
        "policy_snapshots.id",
    }


def test_policy_snapshot_columns_constraints_indexes():
    cols = {c.name for c in PolicySnapshotRow.__table__.columns}
    assert cols == {
        "id",
        "tenant_id",
        "policy_bundle_id",
        "policy_bundle_version",
        "content_hash",
        "captured_at",
        "verdict_decision",
        "verdict_reason",
    }
    constraint_names = {c.name for c in PolicySnapshotRow.__table__.constraints if c.name}
    assert "ck_policy_snapshots_decision" in constraint_names
    idx_names = {ix.name for ix in PolicySnapshotRow.__table__.indexes}
    assert "ix_policy_snapshots_bundle" in idx_names
    assert "ix_policy_snapshots_tenant_captured" in idx_names
    fks = {fk.target_fullname for fk in PolicySnapshotRow.__table__.foreign_keys}
    assert fks == {"tenants.id", "policy_bundles.id"}


def test_all_datetime_columns_are_timezone_aware():
    """Every datetime column must be tz-aware to match Pydantic schema constraints."""
    for table in Base.metadata.tables.values():
        for col in table.columns:
            type_str = str(col.type)
            if "DATETIME" in type_str.upper() or "TIMESTAMP" in type_str.upper():
                # SQLAlchemy 2.0: timezone=True manifests in repr
                assert "TZ=True" in repr(col.type) or "timezone=True" in repr(
                    col.type
                ), f"{table.name}.{col.name} must be timezone=True"


def test_tenant_agents_relationship():
    """TenantRow.agents → AgentRow many-to-one back-populated."""
    rel = inspect(TenantRow).relationships["agents"]
    assert rel.mapper.class_ is AgentRow
    assert rel.back_populates == "tenant"


def test_base_is_declarative():
    """Base must be a DeclarativeBase subclass; sanity ping on metadata presence."""
    assert Base.metadata is not None
    assert len(Base.metadata.tables) == 9  # CP9.43 added ma_export_jobs


def test_timestamp_anchor_columns_and_constraints():
    """CP9.19 / BR-06: new timestamp_anchors table."""
    cols = {c.name for c in TimestampAnchorRow.__table__.columns}
    assert cols == {
        "id",
        "tenant_id",
        "anchor_date",
        "root_hash",
        "tsa_identifier",
        "tsr_bytes",
        "tsa_signature",
        "timestamped_at",
        "anchored_at",
        "status",
    }
    constraint_names = {c.name for c in TimestampAnchorRow.__table__.constraints if c.name}
    assert "uq_timestamp_anchors_tenant_date" in constraint_names
    assert "ck_timestamp_anchors_status" in constraint_names
    idx_names = {ix.name for ix in TimestampAnchorRow.__table__.indexes}
    assert "ix_timestamp_anchors_tenant_anchored" in idx_names
    # FK to tenants only.
    fks = {fk.target_fullname for fk in TimestampAnchorRow.__table__.foreign_keys}
    assert fks == {"tenants.id"}
    # root_hash / tsr_bytes / tsa_signature / timestamped_at are nullable
    # (deferred tombstones leave them NULL).
    assert TimestampAnchorRow.__table__.columns["root_hash"].nullable is True
    assert TimestampAnchorRow.__table__.columns["tsr_bytes"].nullable is True
    assert TimestampAnchorRow.__table__.columns["tsa_signature"].nullable is True
    assert TimestampAnchorRow.__table__.columns["timestamped_at"].nullable is True
    # status and anchored_at are NOT nullable.
    assert TimestampAnchorRow.__table__.columns["status"].nullable is False
    assert TimestampAnchorRow.__table__.columns["anchored_at"].nullable is False


def test_ma_export_job_columns_and_constraints():
    """CP9.43 / IP #8: new ma_export_jobs table."""
    cols = {c.name for c in MaExportJobRow.__table__.columns}
    assert cols == {
        "id",
        "tenant_id",
        "requested_by_agent_id",
        "status",
        "scope_start",
        "scope_end",
        "encrypt_for_pubkey_b64",
        "platform_sign_key_id",
        "requested_at",
        "started_at",
        "completed_at",
        "result_export",
        "result_error",
    }
    constraint_names = {c.name for c in MaExportJobRow.__table__.constraints if c.name}
    assert "ck_ma_export_jobs_status" in constraint_names
    idx_names = {ix.name for ix in MaExportJobRow.__table__.indexes}
    assert "ix_ma_export_jobs_tenant_requested" in idx_names
    assert "ix_ma_export_jobs_status" in idx_names
    fks = {fk.target_fullname for fk in MaExportJobRow.__table__.foreign_keys}
    assert fks == {"tenants.id", "agents.id"}
    # Lifecycle nullability.
    assert MaExportJobRow.__table__.columns["started_at"].nullable is True
    assert MaExportJobRow.__table__.columns["completed_at"].nullable is True
    assert MaExportJobRow.__table__.columns["result_export"].nullable is True
    assert MaExportJobRow.__table__.columns["result_error"].nullable is True
    assert MaExportJobRow.__table__.columns["requested_by_agent_id"].nullable is True
    # Required at creation.
    assert MaExportJobRow.__table__.columns["tenant_id"].nullable is False
    assert MaExportJobRow.__table__.columns["status"].nullable is False
    assert MaExportJobRow.__table__.columns["scope_start"].nullable is False
    assert MaExportJobRow.__table__.columns["scope_end"].nullable is False
    assert MaExportJobRow.__table__.columns["requested_at"].nullable is False

"""Tests for the Alembic initial-schema migration.

Runs alembic upgrade head --sql offline and asserts every expected table,
index, FK, and constraint is present. Pure offline test: no DB needed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def migration_sql() -> str:
    """Run alembic upgrade head --sql and return stdout."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


EXPECTED_TABLES = ["tenants", "agents", "policy_bundles", "events", "receipts"]


@pytest.mark.parametrize("table", EXPECTED_TABLES)
def test_table_created(migration_sql, table):
    assert f"CREATE TABLE {table}" in migration_sql


EXPECTED_INDEXES = [
    "ix_tenants_slug",
    "ix_agents_tenant_id",
    "ix_policy_bundles_tenant_id",
    "ix_policy_bundles_content_hash",
    "ix_events_trace_span",
    "ix_events_tenant_occurred",
    "ix_receipts_event",
    "ix_receipts_tenant_signed",
]


@pytest.mark.parametrize("index_name", EXPECTED_INDEXES)
def test_index_created(migration_sql, index_name):
    assert index_name in migration_sql


EXPECTED_CONSTRAINTS = [
    "uq_tenants_slug",
    "uq_agents_tenant_slug",
    "ck_agents_status",
    "uq_policy_bundles_tenant_version",
    "uq_receipts_tenant_sequence",
    "uq_receipts_receipt_hash",
    "ck_receipts_sequence_nonneg",
]


@pytest.mark.parametrize("constraint_name", EXPECTED_CONSTRAINTS)
def test_constraint_created(migration_sql, constraint_name):
    assert constraint_name in migration_sql


def test_alembic_version_table_present(migration_sql):
    assert "alembic_version" in migration_sql
    assert "0001_initial" in migration_sql


def test_all_fks_use_restrict_ondelete(migration_sql):
    """Append-only ledger: no cascading deletes."""
    # Every ForeignKey in the migration should use ON DELETE RESTRICT
    fk_lines = [ln for ln in migration_sql.splitlines() if "FOREIGN KEY" in ln]
    assert (
        len(fk_lines) >= 6
    )  # tenant_id in agents,pb,events,receipts + agent_id + event_id + pb_id
    for ln in fk_lines:
        assert "ON DELETE RESTRICT" in ln, f"FK without RESTRICT: {ln}"


def test_jsonb_columns_present(migration_sql):
    """payload and content columns must be JSONB for PostgreSQL."""
    assert "payload JSONB NOT NULL" in migration_sql
    assert "content JSONB NOT NULL" in migration_sql


def test_timezone_aware_datetimes(migration_sql):
    """All datetime columns must be TIMESTAMP WITH TIME ZONE."""
    assert "TIMESTAMP WITH TIME ZONE NOT NULL" in migration_sql
    # No naive timestamps should exist
    assert (
        "TIMESTAMP NOT NULL" not in migration_sql
        or "TIMESTAMP WITH TIME ZONE NOT NULL" in migration_sql
    )

"""Tests for packages.ledger.bundle_repository (CP9.14 / NEW-P9.8.24).

Uses mocked AsyncSession (no real Postgres) - same pattern as the other
repository tests in this suite. Each test sets up a session whose
``execute`` returns the rows the test wants and asserts the repo function
returns the correctly-reconstructed PolicyBundle.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from packages.ledger.bundle_repository import (
    get_active_bundle_for_tenant,
    get_bundle_by_id,
    list_bundles_for_tenant,
    write_bundle,
)
from packages.ledger.models import PolicyBundleRow
from packages.schema.policy_bundle import PolicyBundle

_TENANT_A = UUID("11111111-2222-3333-4444-555555555555")
_TENANT_B = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
_SAMPLE_CONTENT = {"rules": [{"kind": "x", "decision": "allow"}], "default": "allow"}


def _make_bundle(
    tenant_id: UUID = _TENANT_A,
    *,
    version: str = "1.0.0",
    created_at: datetime | None = None,
    content: dict | None = None,
) -> PolicyBundle:
    return PolicyBundle(
        id=uuid4(),
        tenant_id=tenant_id,
        version=version,
        content_hash="a" * 64,
        content=content or _SAMPLE_CONTENT,
        created_at=created_at or datetime(2026, 5, 13, 12, 0, tzinfo=UTC),
    )


def _make_row_from_bundle(b: PolicyBundle) -> object:
    row = MagicMock(spec=PolicyBundleRow)
    row.id = b.id
    row.tenant_id = b.tenant_id
    row.version = b.version
    row.content_hash = b.content_hash
    row.content = b.content
    row.created_at = b.created_at
    return row


def _session_returning_scalar_one(returned_row: object | None) -> MagicMock:
    result_mock = MagicMock()
    result_mock.scalar_one_or_none = MagicMock(return_value=returned_row)
    session = MagicMock()
    session.execute = AsyncMock(return_value=result_mock)
    session.add = MagicMock()
    session.flush = AsyncMock(return_value=None)
    return session


def _session_returning_scalars_all(returned_rows: list) -> MagicMock:
    scalars_mock = MagicMock()
    scalars_mock.all = MagicMock(return_value=returned_rows)
    result_mock = MagicMock()
    result_mock.scalars = MagicMock(return_value=scalars_mock)
    session = MagicMock()
    session.execute = AsyncMock(return_value=result_mock)
    return session


# ---------------------------------------------------------------------------
# write_bundle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_write_bundle_adds_row_and_returns_id():
    bundle = _make_bundle()
    session = _session_returning_scalar_one(None)
    returned_id = await write_bundle(session, bundle)
    assert returned_id == bundle.id
    # Exactly one row added + flush awaited
    assert session.add.call_count == 1
    added_row = session.add.call_args[0][0]
    assert added_row.id == bundle.id
    assert added_row.tenant_id == bundle.tenant_id
    assert added_row.version == bundle.version
    assert added_row.content_hash == bundle.content_hash
    assert added_row.content == bundle.content
    session.flush.assert_awaited_once()


# ---------------------------------------------------------------------------
# get_bundle_by_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_bundle_by_id_returns_none_when_not_found():
    session = _session_returning_scalar_one(None)
    found = await get_bundle_by_id(session, uuid4())
    assert found is None


@pytest.mark.asyncio
async def test_get_bundle_by_id_reconstructs_full_bundle():
    bundle = _make_bundle()
    session = _session_returning_scalar_one(_make_row_from_bundle(bundle))
    found = await get_bundle_by_id(session, bundle.id)
    assert found is not None
    assert found.id == bundle.id
    assert found.tenant_id == bundle.tenant_id
    assert found.version == bundle.version
    assert found.content_hash == bundle.content_hash
    assert found.content == bundle.content
    assert found.created_at == bundle.created_at


# ---------------------------------------------------------------------------
# get_active_bundle_for_tenant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_active_bundle_returns_none_for_tenant_with_no_bundles():
    session = _session_returning_scalar_one(None)
    found = await get_active_bundle_for_tenant(session, _TENANT_A)
    assert found is None


@pytest.mark.asyncio
async def test_get_active_bundle_returns_the_row_the_query_yields():
    """The repo trusts the SQL ORDER BY created_at DESC to give it the
    newest row; here we just verify the row mapping back to a PolicyBundle."""
    bundle = _make_bundle(version="2.0.0", created_at=datetime(2026, 5, 14, tzinfo=UTC))
    session = _session_returning_scalar_one(_make_row_from_bundle(bundle))
    found = await get_active_bundle_for_tenant(session, _TENANT_A)
    assert found is not None
    assert found.version == "2.0.0"
    assert found.tenant_id == _TENANT_A


# ---------------------------------------------------------------------------
# list_bundles_for_tenant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_bundles_returns_empty_list_when_none():
    session = _session_returning_scalars_all([])
    bundles = await list_bundles_for_tenant(session, _TENANT_A)
    assert bundles == []


@pytest.mark.asyncio
async def test_list_bundles_returns_reconstructed_bundles_in_query_order():
    b1 = _make_bundle(version="1.0.0", created_at=datetime(2026, 5, 13, tzinfo=UTC))
    b2 = _make_bundle(version="2.0.0", created_at=datetime(2026, 5, 14, tzinfo=UTC))
    b3 = _make_bundle(version="3.0.0", created_at=datetime(2026, 5, 15, tzinfo=UTC))
    # The SQL is ORDER BY created_at DESC so the mock returns newest-first
    rows = [_make_row_from_bundle(b3), _make_row_from_bundle(b2), _make_row_from_bundle(b1)]
    session = _session_returning_scalars_all(rows)
    bundles = await list_bundles_for_tenant(session, _TENANT_A)
    versions = [b.version for b in bundles]
    assert versions == ["3.0.0", "2.0.0", "1.0.0"]


@pytest.mark.asyncio
async def test_list_bundles_respects_limit_param_via_sql():
    """We can't directly observe limit in this mock setup but we can confirm
    the function passes the kwarg through without raising."""
    session = _session_returning_scalars_all([])
    result = await list_bundles_for_tenant(session, _TENANT_A, limit=10)
    assert result == []
    # The compiled statement is what the function passed; check it included LIMIT
    stmt = session.execute.call_args[0][0]
    sql = str(stmt.compile())
    assert "LIMIT" in sql.upper()


# ---------------------------------------------------------------------------
# Cross-tenant isolation - WHERE clause must reference the tenant_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_active_bundle_query_filters_by_tenant_id():
    session = _session_returning_scalar_one(None)
    await get_active_bundle_for_tenant(session, _TENANT_B)
    stmt = session.execute.call_args[0][0]
    compiled = stmt.compile()
    # Tenant id should appear in the bound params
    assert _TENANT_B in compiled.params.values()


@pytest.mark.asyncio
async def test_get_active_bundle_query_filters_on_status_active():
    """CP9.15 regression: the WHERE clause must include ``status = 'active'``
    so only bundles that have walked the full approval workflow are
    considered. Pre-CP9.15 the query returned the most recently created
    bundle regardless of status.
    """
    session = _session_returning_scalar_one(None)
    await get_active_bundle_for_tenant(session, _TENANT_A)
    stmt = session.execute.call_args[0][0]
    compiled = stmt.compile()
    # 'active' should appear as a bound param value
    assert "active" in compiled.params.values()


@pytest.mark.asyncio
async def test_list_bundles_query_filters_by_tenant_id():
    session = _session_returning_scalars_all([])
    await list_bundles_for_tenant(session, _TENANT_B)
    stmt = session.execute.call_args[0][0]
    compiled = stmt.compile()
    assert _TENANT_B in compiled.params.values()

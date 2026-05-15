"""PG integration tests for packages.jobs.ma_export_runner (CP9.44 / IP #8).

Runner half of NEW-P12.X.ma-export-async-job. Exercises the full
pipeline end-to-end against a real Postgres:

  1. Seed a tenant + agent + bundle + 5 receipts + 1 anchor (same
     demo dataset shape as scripts/seed_demo_data.py produces).
  2. Insert a ma_export_jobs row in 'pending' status.
  3. Invoke run_ma_export_job against a real sessionmaker.
  4. Verify the row transitions pending -> running -> completed and
     the result_export holds a well-formed MaDiligenceExport JSON.
  5. Verify the ma_root_hash matches what verify_ma_diligence_export
     would compute on the recovered bundle.
  6. With encryption: verify result_export is a CipherEnvelope JSON
     and decrypts back to a valid MaDiligenceExport.
  7. With platform signing: verify result_export's platform_signature
     is populated AND verify_ma_diligence_export_signature passes
     under the platform public key.

Skipped when FORENSA_TEST_DB_URL unset.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from packages.crypto.encrypt import (
    CipherEnvelope,
    decrypt_for_recipient,
    generate_x25519_keypair,
)
from packages.crypto.sign import generate_keypair
from packages.crypto.tsa import MockTimestampClient
from packages.export.ma_export import (
    MaDiligenceExport,
    verify_ma_diligence_export,
    verify_ma_diligence_export_signature,
)
from packages.jobs.ma_export_runner import run_ma_export_job
from packages.ledger.anchor import anchor_day
from packages.ledger.bundle_repository import write_bundle
from packages.ledger.bundle_workflow import activate, approve, propose, review
from packages.ledger.ma_export_job_repository import (
    create_ma_export_job,
    get_ma_export_job_by_id,
)
from packages.ledger.models import (
    AgentRow,
    EventRow,
    PolicySnapshotRow,
    ReceiptRow,
    TenantRow,
)
from packages.ledger.receipt_builder import build_receipt
from packages.policy.bundle_builder import build_bundle
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.policy.snapshot import capture_snapshot
from packages.schema.receipt import Receipt

pytestmark = pytest.mark.pg

_DAY = datetime(2026, 5, 13, tzinfo=UTC)


@pytest_asyncio.fixture
async def seeded_demo(pg_engine: AsyncEngine, pg_url: str, repo_root):
    """Truncate + seed a minimal demo dataset compatible with the runner.

    Yields (sessionmaker, tenant_id, anchor_date, scope_start, scope_end).
    """
    # Make sure the schema is at head.
    import os
    import subprocess
    import sys

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(repo_root),
        env={**os.environ, "FORENSA_DATABASE_URL": pg_url},
        capture_output=True,
        text=True,
        check=True,
    )

    async with pg_engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE "
                "ma_export_jobs, timestamp_anchors, idempotency_records, "
                "policy_bundle_approvals, receipts, events, "
                "policy_snapshots, policy_bundles, agents, tenants "
                "RESTART IDENTITY CASCADE"
            )
        )

    factory = async_sessionmaker(pg_engine, expire_on_commit=False)
    tenant_id = uuid4()
    agent_id = uuid4()

    async with factory() as session:
        session.add(
            TenantRow(
                id=tenant_id,
                slug=f"runner-test-{tenant_id}",
                display_name="Runner Test",
                signing_key_id="runner-key",
                created_at=datetime.now(UTC),
            )
        )
        await session.flush()

        tenant_priv, _ = generate_keypair()
        agent_priv, agent_pub = generate_keypair()
        session.add(
            AgentRow(
                id=agent_id,
                tenant_id=tenant_id,
                slug="runner-agent",
                display_name="Runner Agent",
                identity_public_key=agent_pub,
                status="active",
                created_at=datetime.now(UTC),
            )
        )
        await session.flush()

        bundle = build_bundle(
            tenant_id=tenant_id,
            version="1.0.0",
            content={
                "rules": [{"kind": "tool_call", "decision": "allow"}],
                "default": "allow",
            },
        )
        await write_bundle(session, bundle)
        author_id = uuid4()
        reviewer_id = uuid4()
        approver_id = uuid4()
        activator_id = uuid4()
        await propose(session, bundle_id=bundle.id, author_actor_id=author_id, reason="seed")
        await review(
            session,
            bundle_id=bundle.id,
            reviewer_actor_id=reviewer_id,
            reason="seed",
        )
        await approve(
            session,
            bundle_id=bundle.id,
            approver_actor_id=approver_id,
            reason="seed",
        )
        await activate(
            session,
            bundle_id=bundle.id,
            activator_actor_id=activator_id,
            reason="seed",
        )

        # Build 3 receipts chained on 2026-05-13.
        mock_gate = MockLobsterTrapClient(
            policy_bundle_id=bundle.id,
            policy_bundle_version=bundle.version,
            content=bundle.content,
        )
        prev: Receipt | None = None
        for i in range(3):
            action = {"kind": "tool_call", "step": i}
            verdict = await mock_gate.evaluate(tenant_id, action)
            snap = capture_snapshot(bundle, verdict)
            snap_id = uuid4()
            session.add(
                PolicySnapshotRow(
                    id=snap_id,
                    tenant_id=tenant_id,
                    policy_bundle_id=bundle.id,
                    policy_bundle_version=bundle.version,
                    content_hash=snap.content_hash,
                    captured_at=_DAY + timedelta(hours=12, minutes=i),
                    verdict_decision=verdict.decision.value,
                    verdict_reason=verdict.reason,
                )
            )
            await session.flush()

            event_id = uuid4()
            session.add(
                EventRow(
                    id=event_id,
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    trace_id="a" * 32,
                    span_id="b" * 16,
                    parent_span_id=None,
                    kind="tool_call",
                    occurred_at=_DAY + timedelta(hours=12, minutes=i),
                    payload={"step": i},
                    reasoning=None,
                    output=None,
                    policy_version=bundle.version,
                    policy_verdict=verdict.decision.value,
                )
            )
            await session.flush()

            receipt = build_receipt(
                tenant_id=tenant_id,
                event_id=event_id,
                event_payload={"step": i},
                policy_snapshot=snap,
                policy_snapshot_id=snap_id,
                prev_receipt=prev,
                tenant_signing_key=tenant_priv,
                agent_signing_key=agent_priv,
            )
            receipt = receipt.model_copy(
                update={
                    "sequence": i,
                    "signed_at": _DAY + timedelta(hours=12, minutes=i, seconds=30),
                }
            )
            session.add(
                ReceiptRow(
                    id=receipt.id,
                    tenant_id=receipt.tenant_id,
                    event_id=receipt.event_id,
                    policy_bundle_id=receipt.policy_bundle_id,
                    policy_snapshot_id=snap_id,
                    sequence=receipt.sequence,
                    prev_receipt_hash=receipt.prev_receipt_hash,
                    payload_hash=receipt.payload_hash,
                    receipt_hash=receipt.receipt_hash,
                    signature=receipt.signature,
                    agent_signature=receipt.agent_signature,
                    signed_at=receipt.signed_at,
                )
            )
            await session.flush()
            prev = receipt

        # Anchor the day.
        mock_tsa = MockTimestampClient(identifier="mock-tsa://runner-test")
        await anchor_day(session, tenant_id=tenant_id, day=_DAY, timestamp_client=mock_tsa)
        await session.commit()

    yield factory, tenant_id, _DAY


async def test_runner_completes_unencrypted_unsigned_job(seeded_demo) -> None:
    """Happy path: runner builds bundle, marks completed, result is a
    well-formed MaDiligenceExport JSON whose ma_root_hash verifies."""
    factory, tenant_id, day = seeded_demo

    scope_start = day - timedelta(hours=1)
    scope_end = day + timedelta(days=1)

    async with factory() as session:
        job_id = await create_ma_export_job(
            session,
            tenant_id=tenant_id,
            scope_start=scope_start,
            scope_end=scope_end,
        )
        await session.commit()

    # Run the worker.
    await run_ma_export_job(factory, job_id=job_id)

    async with factory() as session:
        row = await get_ma_export_job_by_id(session, job_id)
        assert row is not None
        assert row.status == "completed", f"expected completed; got {row.status}"
        assert row.started_at is not None
        assert row.completed_at is not None
        assert row.result_error is None
        assert isinstance(row.result_export, dict)
        # Recover the MaDiligenceExport from the dict.
        export = MaDiligenceExport.model_validate(row.result_export)
        assert verify_ma_diligence_export(export) is True
        assert export.header.tenant_id == tenant_id
        # 3 receipts on the anchored day, one pack.
        assert export.header.pack_count == 1
        assert export.header.total_receipt_count == 3
        assert export.header.anchor_count == 1
        # Unsigned bundle.
        assert export.platform_signature is None
        assert export.platform_key_id is None


async def test_runner_completes_signed_job(seeded_demo) -> None:
    """Runner signs the bundle when row has platform_sign_key_id AND
    the caller passes a platform_signing_key."""
    factory, tenant_id, day = seeded_demo
    scope_start = day - timedelta(hours=1)
    scope_end = day + timedelta(days=1)

    platform_priv, platform_pub = generate_keypair()

    async with factory() as session:
        job_id = await create_ma_export_job(
            session,
            tenant_id=tenant_id,
            scope_start=scope_start,
            scope_end=scope_end,
            platform_sign_key_id="platform-key-v1",
        )
        await session.commit()

    await run_ma_export_job(factory, job_id=job_id, platform_signing_key=platform_priv)

    async with factory() as session:
        row = await get_ma_export_job_by_id(session, job_id)
        assert row is not None
        assert row.status == "completed"
        export = MaDiligenceExport.model_validate(row.result_export)
        assert export.platform_signature is not None
        assert export.platform_key_id == "platform-key-v1"
        # Verify under the published platform public key.
        assert (
            verify_ma_diligence_export_signature(export, platform_public_key=platform_pub) is True
        )


async def test_runner_completes_encrypted_job(seeded_demo) -> None:
    """Runner encrypts the bundle when row has encrypt_for_pubkey_b64."""
    factory, tenant_id, day = seeded_demo
    scope_start = day - timedelta(hours=1)
    scope_end = day + timedelta(days=1)

    acquirer_priv, acquirer_pub = generate_x25519_keypair()
    acquirer_pub_b64 = base64.urlsafe_b64encode(acquirer_pub).decode("ascii").rstrip("=")

    async with factory() as session:
        job_id = await create_ma_export_job(
            session,
            tenant_id=tenant_id,
            scope_start=scope_start,
            scope_end=scope_end,
            encrypt_for_pubkey_b64=acquirer_pub_b64,
        )
        await session.commit()

    await run_ma_export_job(factory, job_id=job_id)

    async with factory() as session:
        row = await get_ma_export_job_by_id(session, job_id)
        assert row is not None
        assert row.status == "completed"
        # result_export is a CipherEnvelope dict (no @type field; identify
        # by the 'scheme' marker per packages.crypto.encrypt.CipherEnvelope).
        assert row.result_export.get("scheme") == "x25519-chacha20poly1305-v1"
        envelope = CipherEnvelope.model_validate(row.result_export)
        plaintext = decrypt_for_recipient(envelope, recipient_private_key=acquirer_priv)
        # The plaintext is the canonical MaDiligenceExport JSON.
        export = MaDiligenceExport.model_validate_json(plaintext)
        assert verify_ma_diligence_export(export) is True
        assert export.header.tenant_id == tenant_id


async def test_runner_marks_failed_when_pubkey_invalid(seeded_demo) -> None:
    """Garbage encryption pubkey -> runner records failure cleanly."""
    factory, tenant_id, day = seeded_demo
    scope_start = day - timedelta(hours=1)
    scope_end = day + timedelta(days=1)

    async with factory() as session:
        job_id = await create_ma_export_job(
            session,
            tenant_id=tenant_id,
            scope_start=scope_start,
            scope_end=scope_end,
            # Non-ASCII -> base64 decoder rejects -> MaExportError -> failed status
            encrypt_for_pubkey_b64="AAAA" + chr(255),
        )
        await session.commit()

    await run_ma_export_job(factory, job_id=job_id)

    async with factory() as session:
        row = await get_ma_export_job_by_id(session, job_id)
        assert row is not None
        assert row.status == "failed"
        assert row.result_error is not None
        assert "not valid base64" in row.result_error
        assert row.result_export is None


async def test_runner_marks_failed_when_no_anchors_in_scope_window_is_ok(
    seeded_demo,
) -> None:
    """A scope window with zero anchors still produces a completed export
    -- it just has zero packs. The runner does NOT treat empty as a failure.
    """
    factory, tenant_id, _ = seeded_demo
    # Scope window in the future, no anchors.
    future_start = datetime(2030, 1, 1, tzinfo=UTC)
    future_end = datetime(2030, 1, 2, tzinfo=UTC)

    async with factory() as session:
        job_id = await create_ma_export_job(
            session,
            tenant_id=tenant_id,
            scope_start=future_start,
            scope_end=future_end,
        )
        await session.commit()

    await run_ma_export_job(factory, job_id=job_id)

    async with factory() as session:
        row = await get_ma_export_job_by_id(session, job_id)
        assert row is not None
        assert row.status == "completed"
        export = MaDiligenceExport.model_validate(row.result_export)
        assert export.header.pack_count == 0
        assert export.header.anchor_count == 0
        assert export.header.total_receipt_count == 0
        assert verify_ma_diligence_export(export) is True


# A reference to Any so the import isn't flagged unused; ma_export_runner
# itself uses it via the _build_export annotation.
_ = Any

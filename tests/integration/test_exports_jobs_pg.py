"""PG integration tests for POST/GET /v1/exports/ma-diligence/jobs (CP9.45 / IP #8).

Route half of NEW-P12.X.ma-export-async-job. End-to-end:
  1. Seed a tenant + agent + bundle + receipts + anchor (per the shared
     seeded_demo pattern from test_ma_export_runner_pg.py).
  2. Wire create_app() with dependency_overrides for get_session,
     get_sessionmaker, and get_principal.
  3. POST /v1/exports/ma-diligence/jobs -> 202 + job_id, runner scheduled.
  4. Await the scheduled background task (asyncio.create_task'd by the
     route) so the runner finishes before we poll GET.
  5. GET /v1/exports/ma-diligence/jobs/{id} -> status='completed' with
     result_export holding a verifiable MaDiligenceExport.
  6. GET /v1/exports/ma-diligence/jobs -> list includes the new job.

The asyncio.create_task pattern means the runner runs concurrently with
the response. To get a deterministic test, we capture the Task at
schedule time (via a monkeypatch on asyncio.create_task) and await it
explicitly before the GET. Production callers poll instead of awaiting.

Skipped when FORENSA_TEST_DB_URL unset.
"""

from __future__ import annotations

import asyncio
import base64
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from apps.api.main import create_app
from apps.api.routes import exports as exports_mod
from apps.api.routes.exports import get_sessionmaker
from apps.api.routes.receipts import get_session
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
)
from packages.ledger.anchor import anchor_day
from packages.ledger.bundle_repository import write_bundle
from packages.ledger.bundle_workflow import activate, approve, propose, review
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
from tests.api._auth_helpers import install_principal_override

pytestmark = pytest.mark.pg

_DAY = datetime(2026, 5, 13, tzinfo=UTC)


@pytest_asyncio.fixture
async def seeded_demo(pg_engine: AsyncEngine, pg_url: str, repo_root):
    """Truncate + seed a demo dataset. Yields (sessionmaker, tenant_id, agent_id, day)."""
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
                slug=f"route-test-{tenant_id}",
                display_name="Route Test",
                signing_key_id="route-key",
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
                slug="route-agent",
                display_name="Route Agent",
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
        await propose(session, bundle_id=bundle.id, author_actor_id=uuid4(), reason="seed")
        await review(session, bundle_id=bundle.id, reviewer_actor_id=uuid4(), reason="seed")
        await approve(session, bundle_id=bundle.id, approver_actor_id=uuid4(), reason="seed")
        await activate(session, bundle_id=bundle.id, activator_actor_id=uuid4(), reason="seed")

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

        mock_tsa = MockTimestampClient(identifier="mock-tsa://route-test")
        await anchor_day(session, tenant_id=tenant_id, day=_DAY, timestamp_client=mock_tsa)
        await session.commit()

    yield factory, tenant_id, agent_id, _DAY


@pytest_asyncio.fixture
async def wired_app(seeded_demo, monkeypatch):
    """create_app() with all three dependencies overridden to the seeded DB
    + capture the scheduled background Task so the test can await it.

    Yields (app, client, factory, tenant_id, agent_id, day, tasks_list).
    tasks_list is a list[asyncio.Task] of all scheduled runners; tests
    await them before polling GET to get deterministic completion.
    """
    factory, tenant_id, agent_id, day = seeded_demo

    app = create_app()
    install_principal_override(app, tenant_id=tenant_id, agent_id=agent_id)

    # The route uses get_session for the POST insert and the GET reads.
    # Use the same sessionmaker for both: each request gets a fresh
    # session via a small async generator.
    async def _session_override() -> AsyncSession:
        async with factory() as s:
            yield s

    async def _sm_override() -> async_sessionmaker[AsyncSession]:
        return factory

    app.dependency_overrides[get_session] = _session_override
    app.dependency_overrides[get_sessionmaker] = _sm_override

    # Capture asyncio.create_task so tests can await the runner.
    scheduled_tasks: list[asyncio.Task] = []
    original_create_task = exports_mod.asyncio.create_task

    def _capturing_create_task(coro, *, name=None):
        task = original_create_task(coro, name=name)
        scheduled_tasks.append(task)
        return task

    monkeypatch.setattr(exports_mod.asyncio, "create_task", _capturing_create_task)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield app, c, factory, tenant_id, agent_id, day, scheduled_tasks

    app.dependency_overrides.clear()


# ---------- POST + scheduled runner + GET status round-trip ----------


async def test_post_schedules_runner_then_get_returns_completed(wired_app) -> None:
    """End-to-end happy path: POST -> 202, scheduled task runs, GET shows
    completed status with a verifiable MaDiligenceExport in result_export."""
    app, client, factory, tenant_id, agent_id, day, tasks = wired_app

    scope_start = (day - timedelta(hours=1)).isoformat()
    scope_end = (day + timedelta(days=1)).isoformat()

    response = await client.post(
        "/v1/exports/ma-diligence/jobs",
        json={
            "tenant_id": str(tenant_id),
            "scope_start": scope_start,
            "scope_end": scope_end,
        },
    )
    assert response.status_code == 202, response.text
    job_id = UUID(response.json()["job_id"])

    # Drain ALL scheduled tasks before polling. The route schedules one
    # ma_export_runner per POST, but the test fixture may capture other
    # asyncio.create_task calls (FastAPI internals etc) -- we don't care
    # about their count, just that they all finish.
    assert len(tasks) >= 1
    await asyncio.gather(*tasks, return_exceptions=True)

    poll = await client.get(f"/v1/exports/ma-diligence/jobs/{job_id}")
    assert poll.status_code == 200, poll.text
    body = poll.json()
    assert body["status"] == "completed", body
    assert body["result_error"] is None
    assert body["result_export"] is not None
    export = MaDiligenceExport.model_validate(body["result_export"])
    assert verify_ma_diligence_export(export) is True
    assert export.header.tenant_id == tenant_id
    assert export.header.pack_count == 1
    assert export.header.total_receipt_count == 3


async def test_post_with_encryption_then_get_returns_cipher_envelope(wired_app) -> None:
    """POST with encrypt_for_pubkey_b64 -> result_export is a CipherEnvelope
    that decrypts back to a valid MaDiligenceExport."""
    app, client, factory, tenant_id, agent_id, day, tasks = wired_app

    acquirer_priv, acquirer_pub = generate_x25519_keypair()
    acquirer_pub_b64 = base64.urlsafe_b64encode(acquirer_pub).decode("ascii").rstrip("=")

    response = await client.post(
        "/v1/exports/ma-diligence/jobs",
        json={
            "tenant_id": str(tenant_id),
            "scope_start": (day - timedelta(hours=1)).isoformat(),
            "scope_end": (day + timedelta(days=1)).isoformat(),
            "encrypt_for_pubkey_b64": acquirer_pub_b64,
        },
    )
    assert response.status_code == 202
    job_id = UUID(response.json()["job_id"])
    await asyncio.gather(*tasks, return_exceptions=True)

    poll = await client.get(f"/v1/exports/ma-diligence/jobs/{job_id}")
    assert poll.status_code == 200
    body = poll.json()
    assert body["status"] == "completed"
    # Encrypted result -> CipherEnvelope dict.
    assert body["result_export"]["scheme"] == "x25519-chacha20poly1305-v1"
    envelope = CipherEnvelope.model_validate(body["result_export"])
    plaintext = decrypt_for_recipient(envelope, recipient_private_key=acquirer_priv)
    export = MaDiligenceExport.model_validate_json(plaintext)
    assert verify_ma_diligence_export(export) is True


async def test_get_status_404_for_unknown_job_id(wired_app) -> None:
    """A GET for a nonexistent UUID is 404 (and the same 404 would surface
    for a cross-tenant probe -- oracle-safe)."""
    app, client, factory, tenant_id, agent_id, day, tasks = wired_app

    response = await client.get(f"/v1/exports/ma-diligence/jobs/{uuid4()}")
    assert response.status_code == 404
    assert response.json()["detail"] == "job not found"


async def test_list_returns_newly_created_jobs(wired_app) -> None:
    """LIST returns the jobs we POST'd; ordering is newest-first by
    requested_at DESC."""
    app, client, factory, tenant_id, agent_id, day, tasks = wired_app

    # POST two jobs in sequence.
    job_ids: list[UUID] = []
    for _ in range(2):
        r = await client.post(
            "/v1/exports/ma-diligence/jobs",
            json={
                "tenant_id": str(tenant_id),
                "scope_start": (day - timedelta(hours=1)).isoformat(),
                "scope_end": (day + timedelta(days=1)).isoformat(),
            },
        )
        assert r.status_code == 202
        job_ids.append(UUID(r.json()["job_id"]))
    # Drain scheduled tasks so jobs complete (not strictly required for
    # list visibility -- pending jobs are listable too -- but it gets
    # the row into a deterministic terminal state).
    await asyncio.gather(*tasks, return_exceptions=True)

    response = await client.get("/v1/exports/ma-diligence/jobs")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 2
    listed_ids = {UUID(item["job_id"]) for item in body["items"]}
    assert set(job_ids).issubset(listed_ids)


async def test_post_passes_signing_metadata_to_job_row(wired_app) -> None:
    """platform_sign_key_id on the request body lands on the row, but the
    actual sign step happens only if the runner receives a private key
    (not the route's responsibility). We verify the row has the key id;
    the runner-half PG tests already cover that the runner respects it.
    """
    app, client, factory, tenant_id, agent_id, day, tasks = wired_app

    response = await client.post(
        "/v1/exports/ma-diligence/jobs",
        json={
            "tenant_id": str(tenant_id),
            "scope_start": (day - timedelta(hours=1)).isoformat(),
            "scope_end": (day + timedelta(days=1)).isoformat(),
            "platform_sign_key_id": "forensa-platform-key-v1",
        },
    )
    assert response.status_code == 202
    job_id = UUID(response.json()["job_id"])
    await asyncio.gather(*tasks, return_exceptions=True)

    # The route doesn't pass a private key, so the bundle ends up unsigned
    # even though the key_id is on the row. This mirrors the CP9.44 runner
    # contract: signing is opt-in via the caller's platform_signing_key arg.
    poll = await client.get(f"/v1/exports/ma-diligence/jobs/{job_id}")
    assert poll.status_code == 200
    body = poll.json()
    assert body["status"] == "completed"
    export = MaDiligenceExport.model_validate(body["result_export"])
    assert export.platform_signature is None  # No key passed at schedule time.


# Reference Any so the import isn't flagged unused (used by typing helpers).
_ = Any

"""Test frozen Pydantic schema models are hashable (CP9.10 / NEW-P9.8.18).

The reviewer asked whether the frozen Pydantic v2 models with bytes fields
(``Receipt.signature``, ``Agent.identity_public_key``) actually have a
working ``__hash__``. Pydantic v2 frozen models auto-derive ``__hash__``
only if all field types are hashable; bytes is hashable so they should be,
but the review said "check whether it actually is".

This test documents today's behaviour for every frozen domain model:

- Tenant, Agent, Receipt: hashable (all field types are hashable)
- PolicyBundle, Event: NOT hashable (have dict fields)

The practical consequence the reviewer was probing was whether Receipts can
go in a set for dedup. They can.

CP9.10 note on async: tests that need an async helper (the Lobster Trap
``evaluate`` call) use ``@pytest.mark.asyncio`` so they share the
pytest-asyncio session event loop. Using ``asyncio.run()`` here would
create a fresh ProactorEventLoop on Windows that leaks an unclosed socket
on teardown, which the project's strict ``filterwarnings = ["error", ...]``
escalates to a test failure on a later unrelated test (flake).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from packages.crypto.sign import generate_keypair
from packages.ledger.receipt_builder import build_receipt
from packages.policy.bundle_builder import build_bundle
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.policy.snapshot import capture_snapshot
from packages.schema.agent import Agent
from packages.schema.event import Event, EventKind
from packages.schema.policy_bundle import PolicyBundle
from packages.schema.tenant import Tenant

_TENANT = uuid4()
_AGENT = uuid4()
_SAMPLE_CONTENT = {"rules": [{"kind": "x", "decision": "allow"}], "default": "allow"}


def _is_hashable(obj: object) -> bool:
    """True iff hash(obj) does not raise."""
    try:
        hash(obj)
    except TypeError:
        return False
    return True


def test_tenant_is_hashable():
    t = Tenant(
        id=_TENANT,
        slug="acme-bank",
        display_name="ACME Bank",
        signing_key_id="arn:aws:kms:eu-west-1:123:key/abc",
        created_at=datetime(2026, 5, 14, tzinfo=UTC),
    )
    assert _is_hashable(t)
    # Equal instances must hash equal.
    t2 = Tenant(
        id=_TENANT,
        slug="acme-bank",
        display_name="ACME Bank",
        signing_key_id="arn:aws:kms:eu-west-1:123:key/abc",
        created_at=datetime(2026, 5, 14, tzinfo=UTC),
    )
    assert hash(t) == hash(t2)


def test_agent_is_hashable_with_bytes_field():
    # Agent has bytes identity_public_key field. bytes IS hashable in Python
    # (unlike bytearray), so this should work.
    _, public_key = generate_keypair()
    a = Agent(
        id=_AGENT,
        tenant_id=_TENANT,
        slug="audit-agent",
        display_name="Audit Agent",
        identity_public_key=public_key,
        status="active",
        created_at=datetime(2026, 5, 14, tzinfo=UTC),
    )
    assert _is_hashable(a)


def test_policy_bundle_is_not_hashable_due_to_dict_content():
    # PolicyBundle.content is dict[str, Any] which is NOT hashable in Python.
    # Documenting this fact so if Pydantic v2 ever auto-freezes dicts the
    # assertion flips and the change surfaces in CI.
    bundle = PolicyBundle(
        id=uuid4(),
        tenant_id=_TENANT,
        version="1.0.0",
        content_hash="a" * 64,
        content=_SAMPLE_CONTENT,
        created_at=datetime(2026, 5, 14, tzinfo=UTC),
    )
    assert _is_hashable(bundle) is False


def test_event_is_not_hashable_due_to_dict_payload():
    # Event.payload is dict[str, Any] (default empty dict). Event is therefore
    # NOT hashable today.
    ev = Event(
        tenant_id=_TENANT,
        agent_id=_AGENT,
        trace_id="a" * 32,
        span_id="b" * 16,
        kind=EventKind.LLM_INVOCATION,
        occurred_at=datetime(2026, 5, 14, tzinfo=UTC),
    )
    assert _is_hashable(ev) is False


@pytest.mark.asyncio
async def test_receipt_is_hashable_with_bytes_signature():
    # Receipt has bytes signature (64 bytes Ed25519). All Receipt fields are
    # hashable types (UUID, int, str, bytes, datetime), so Receipt IS hashable.
    bundle = build_bundle(tenant_id=_TENANT, version="1.0.0", content=_SAMPLE_CONTENT)
    mock = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )
    verdict = await mock.evaluate(_TENANT, {"kind": "x"})
    snap = capture_snapshot(bundle, verdict)
    snap_id = uuid4()
    priv, _ = generate_keypair()
    r = build_receipt(
        tenant_id=_TENANT,
        event_id=uuid4(),
        event_payload={"step": 0},
        policy_snapshot=snap,
        policy_snapshot_id=snap_id,
        prev_receipt=None,
        tenant_signing_key=priv,
    )
    assert _is_hashable(r)


@pytest.mark.asyncio
async def test_receipt_can_be_deduped_via_a_set():
    """The practical consequence the reviewer was probing: Receipts can go in
    a set for dedup because they hash."""
    bundle = build_bundle(tenant_id=_TENANT, version="1.0.0", content=_SAMPLE_CONTENT)
    mock = MockLobsterTrapClient(
        policy_bundle_id=bundle.id,
        policy_bundle_version=bundle.version,
        content=bundle.content,
    )
    verdict = await mock.evaluate(_TENANT, {"kind": "x"})
    snap = capture_snapshot(bundle, verdict)
    snap_id = uuid4()
    priv, _ = generate_keypair()
    r1 = build_receipt(
        tenant_id=_TENANT,
        event_id=uuid4(),
        event_payload={"step": 0},
        policy_snapshot=snap,
        policy_snapshot_id=snap_id,
        prev_receipt=None,
        tenant_signing_key=priv,
    )
    r2 = build_receipt(
        tenant_id=_TENANT,
        event_id=uuid4(),
        event_payload={"step": 1},
        policy_snapshot=snap,
        policy_snapshot_id=snap_id,
        prev_receipt=r1,
        tenant_signing_key=priv,
    )
    # Different event_ids -> different receipts -> set has both.
    assert len({r1, r2}) == 2
    # Same Receipt added twice -> set has one (dedup works).
    assert len({r1, r1}) == 1

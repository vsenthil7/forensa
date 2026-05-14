"""Ingest service: orchestrate end-to-end event persistence (CP9.11).

Pulls together the four pieces of the ingest path so the POST /v1/events
route doesn't have to know about any of them individually:

1. **Resolve the active policy bundle** for the tenant via a
   ``PolicyBundleProvider`` (today: in-memory fallback that returns a
   default deny-nothing bundle; future: real ``policy_bundle_repository``
   landing in ``NEW-P9.8.24``).
2. **Evaluate the action** via the wired ``PolicyEnforcementClient`` (today:
   ``MockLobsterTrapClient`` via override; future: real Veea HTTP client
   landing in ``NEW-P9.8.22``).
3. **Resolve the tenant signing key** via a ``TenantSigningKeyProvider``
   (today: per-tenant in-memory cache keyed by ``Tenant.signing_key_id``;
   future: AWS KMS / GCP Vault adapter landing in ``CP11.1``).
4. **Build the Receipt and atomically persist (snapshot, event, receipt)**
   via ``write_event_with_receipt`` with the snapshot_id allocated by THIS
   service so the receipt_hash binds the same id that the persisted snapshot
   row carries (CP9.11 fix to the original 2-uuid4-call drift).

All three providers are abstract today so the service is unit-testable with
mocks and the real implementations slot in transparently in later phases.

Returns a frozen ``IngestResult`` carrying ``event_id``, ``receipt_id``,
``policy_snapshot_id``, and the boolean ``integrity_ok`` from a live
``recompute_receipt_hash`` check (the same check the GET /v1/receipts/{id}
detail endpoint performs).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Any, ClassVar
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from packages.crypto.sign import generate_keypair
from packages.ledger.bundle_repository import (
    get_active_bundle_for_tenant,
    write_bundle,
)
from packages.ledger.bundle_workflow import (
    activate as workflow_activate,
)
from packages.ledger.bundle_workflow import (
    approve as workflow_approve,
)
from packages.ledger.bundle_workflow import (
    propose as workflow_propose,
)
from packages.ledger.bundle_workflow import (
    review as workflow_review,
)
from packages.ledger.receipt_builder import build_receipt, recompute_receipt_hash
from packages.ledger.repositories import (
    get_latest_receipt_for_tenant,
    write_event_with_receipt,
)
from packages.policy.bundle_builder import build_bundle
from packages.policy.enforcement import PolicyEnforcementClient
from packages.policy.snapshot import capture_snapshot
from packages.schema.event import Event
from packages.schema.policy_bundle import PolicyBundle

# ---------------------------------------------------------------------------
# Provider abstractions - replaceable in production wiring
# ---------------------------------------------------------------------------


class IngestServiceError(RuntimeError):
    """Raised when the ingest pipeline cannot complete a request."""


class PolicyBundleProvider(ABC):
    """Resolves the policy bundle currently active for a tenant.

    Production impl lands in ``NEW-P9.8.24 policy-bundle-persistence`` as a
    repository over ``PolicyBundleRow``. Today's fallback returns a
    deny-nothing default bundle so the ingest path can be exercised end-to-end.
    """

    @abstractmethod
    async def get_active_bundle(self, tenant_id: UUID) -> PolicyBundle:
        """Return the active ``PolicyBundle`` for ``tenant_id``."""


class TenantSigningKeyProvider(ABC):
    """Resolves the Ed25519 signing key bytes for a tenant.

    Production impl lands in ``CP11.1 HSM-backed signing keys`` (KMS adapter).
    Today's fallback is a per-tenant in-memory cache for tests / demo.
    """

    @abstractmethod
    async def get_signing_key(self, tenant_id: UUID) -> bytes:
        """Return the 32-byte Ed25519 private key for ``tenant_id``."""


# ---------------------------------------------------------------------------
# Default in-memory providers (for tests / hackathon demo)
# ---------------------------------------------------------------------------


class DefaultBundleProvider(PolicyBundleProvider):
    """Returns a deny-nothing default ``PolicyBundle`` per tenant.

    Deterministic content so the ``content_hash`` is stable across calls -
    receipts produced under the default bundle are reproducibly verifiable.

    NOT for production. Lands as ``NEW-P9.8.24``-backed repo when policy
    bundle persistence ships.
    """

    _DEFAULT_CONTENT: ClassVar[dict[str, Any]] = {
        "rules": [
            {"kind": "deny_kind", "decision": "deny"},
            {"kind": "escalate_kind", "decision": "escalate"},
        ],
        "default": "allow",
    }

    def __init__(self) -> None:
        self._cache: dict[UUID, PolicyBundle] = {}

    async def get_active_bundle(self, tenant_id: UUID) -> PolicyBundle:
        cached = self._cache.get(tenant_id)
        if cached is not None:
            return cached
        bundle = build_bundle(
            tenant_id=tenant_id,
            version="1.0.0",
            content=self._DEFAULT_CONTENT,
        )
        self._cache[tenant_id] = bundle
        return bundle


class InMemorySigningKeyProvider(TenantSigningKeyProvider):
    """In-memory tenant -> signing-key map for tests and demo.

    Generates a fresh keypair the first time a tenant is requested; caches
    the private key bytes for subsequent calls in the same process. Receipts
    produced this way are verifiable within one process lifetime but DO NOT
    survive a restart - production needs the KMS adapter from ``CP11.1``.
    """

    def __init__(self) -> None:
        self._cache: dict[UUID, bytes] = {}

    async def get_signing_key(self, tenant_id: UUID) -> bytes:
        cached = self._cache.get(tenant_id)
        if cached is not None:
            return cached
        priv, _ = generate_keypair()
        self._cache[tenant_id] = priv
        return priv


class PostgresBundleProvider(PolicyBundleProvider):
    """Production ``PolicyBundleProvider`` backed by the bundle repository
    (CP9.14 / NEW-P9.8.24).

    On each ``get_active_bundle`` call, resolves the bundle in
    ``status='active'`` for the tenant via ``get_active_bundle_for_tenant``.
    If no active bundle exists yet, falls back to building and persisting a
    deny-nothing default bundle (the same content shape
    ``DefaultBundleProvider`` uses) so the ingest pipeline can run
    end-to-end for a brand-new tenant.

    CP9.15: ``get_active_bundle_for_tenant`` now filters on
    ``status='active'``. Fresh bundles default to ``status='proposed'``, so
    the cache-miss bootstrap path must walk the bundle through the approval
    workflow if it wants subsequent calls to find it. The ``auto_activate``
    constructor flag controls this:

    - ``auto_activate=True`` (the hackathon-demo default): the bootstrap
      bundle is walked propose -> review -> approve -> activate by a
      synthetic ``system`` actor so the demo path keeps working with a
      single get_active_bundle call.
    - ``auto_activate=False`` (production-correct): the bootstrap bundle is
      only persisted in ``proposed`` status. Callers are responsible for
      walking it through the workflow via
      ``packages.ledger.bundle_workflow`` calls with real reviewer /
      approver actors. Subsequent ``get_active_bundle`` calls will continue
      to return the freshly-built (in-memory) bundle until the workflow
      completes; the in-memory return preserves the demo behaviour without
      lying about DB state.

    The provider takes an ``AsyncSession`` factory (a zero-arg callable that
    returns a session-scope context manager). This shape avoids coupling the
    provider to the request-scoped ``Depends(get_session)`` - the provider
    can be constructed once at app startup and reused.

    For the hackathon demo today, the default ``DefaultBundleProvider``
    in-memory cache is still wired in ``routes/events.py`` so demos don't
    need a live DB. Swapping to this Postgres impl is one line at app
    factory time.
    """

    def __init__(
        self,
        session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
        *,
        fallback_content: dict[str, Any] | None = None,
        auto_activate: bool = True,
    ) -> None:
        self._session_factory = session_factory
        if fallback_content is not None:
            self._fallback_content: dict[str, Any] = fallback_content
        else:
            self._fallback_content = DefaultBundleProvider._DEFAULT_CONTENT
        self._auto_activate = auto_activate

    async def get_active_bundle(self, tenant_id: UUID) -> PolicyBundle:
        async with self._session_factory() as session:
            existing = await get_active_bundle_for_tenant(session, tenant_id)
            if existing is not None:
                return existing
            # No active bundle yet for this tenant - build and persist a
            # default in 'proposed' status.
            bundle = build_bundle(
                tenant_id=tenant_id,
                version="1.0.0",
                content=self._fallback_content,
            )
            await write_bundle(session, bundle)

            if self._auto_activate:
                # Walk the bundle through the approval workflow with a
                # synthetic system actor so subsequent get_active_bundle
                # calls find it via status='active'. Production callers who
                # want real reviewer / approver identities should set
                # auto_activate=False and drive the workflow themselves.
                system_actor = uuid4()
                await workflow_propose(
                    session,
                    bundle_id=bundle.id,
                    author_actor_id=system_actor,
                    reason="auto-bootstrap by PostgresBundleProvider",
                )
                await workflow_review(
                    session,
                    bundle_id=bundle.id,
                    reviewer_actor_id=system_actor,
                    reason="auto-bootstrap by PostgresBundleProvider",
                )
                await workflow_approve(
                    session,
                    bundle_id=bundle.id,
                    approver_actor_id=system_actor,
                    reason="auto-bootstrap by PostgresBundleProvider",
                )
                await workflow_activate(
                    session,
                    bundle_id=bundle.id,
                    activator_actor_id=system_actor,
                    reason="auto-bootstrap by PostgresBundleProvider",
                )
            return bundle


# ---------------------------------------------------------------------------
# Service result + entry point
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IngestResult:
    """Outcome of one ingest call. Frozen so callers cannot mutate fields."""

    event_id: UUID
    receipt_id: UUID
    policy_snapshot_id: UUID
    receipt_hash: str
    integrity_ok: bool


async def ingest_event(
    *,
    session: AsyncSession,
    event: Event,
    enforcement_client: PolicyEnforcementClient,
    bundle_provider: PolicyBundleProvider,
    signing_key_provider: TenantSigningKeyProvider,
) -> IngestResult:
    """Persist an event end-to-end and return the ``IngestResult``.

    Pipeline:

    1. Resolve the active policy bundle for the tenant.
    2. Evaluate the event's ``kind`` (and ``payload``) against the enforcement
       gateway; capture the verdict into a ``PolicySnapshot``.
    3. **Pre-allocate** the snapshot_id so the receipt_hash can bind it
       BEFORE the row is persisted. The repo accepts the externally-allocated
       id via the ``snapshot_id`` kwarg (CP9.11 refactor).
    4. Fetch the latest Receipt for the tenant (the chain head); ``None`` at
       genesis.
    5. Build the new Receipt: sequence = prev + 1, prev_hash linked,
       receipt_hash computed over the canonical bind including the
       pre-allocated snapshot_id, Ed25519-signed by the tenant's signing key.
    6. Atomically persist (snapshot, event, receipt) via
       ``write_event_with_receipt`` with the pre-allocated snapshot_id.
    7. Live-verify integrity via ``recompute_receipt_hash`` so the caller
       knows the chain is consistent at the moment of write.

    Raises ``IngestServiceError`` on policy / persistence failures so the
    route can map them to HTTP status without leaking internal traceback.
    """
    # 1 - active bundle
    bundle = await bundle_provider.get_active_bundle(event.tenant_id)

    # 2 - evaluate + snapshot
    action = {"kind": str(event.kind), "payload": event.payload}
    try:
        verdict = await enforcement_client.evaluate(event.tenant_id, action)
    except Exception as exc:
        raise IngestServiceError(f"policy enforcement failed: {exc}") from exc
    if verdict.policy_bundle_id != bundle.id:
        # Bundle drift between provider read and evaluator read - refuse.
        raise IngestServiceError("policy verdict references a different bundle than the active one")
    snapshot = capture_snapshot(bundle, verdict)

    # 3 - pre-allocate snapshot_id so the receipt_hash binds it.
    snapshot_id = uuid4()

    # 4 - chain head
    prev_receipt = await get_latest_receipt_for_tenant(session, event.tenant_id)

    # 5 - build + sign with the pre-allocated snapshot_id
    signing_key = await signing_key_provider.get_signing_key(event.tenant_id)
    receipt = build_receipt(
        tenant_id=event.tenant_id,
        event_id=event.id,
        event_payload=event.payload,
        policy_snapshot=snapshot,
        policy_snapshot_id=snapshot_id,
        prev_receipt=prev_receipt,
        tenant_signing_key=signing_key,
    )

    # 6 - persist (snapshot, event, receipt) atomically with the same id
    real_snapshot_id = await write_event_with_receipt(
        session,
        event=event,
        snapshot=snapshot,
        receipt=receipt,
        snapshot_id=snapshot_id,
    )
    # Sanity: repo must echo back the id we passed in.
    if real_snapshot_id != snapshot_id:  # pragma: no cover - defensive
        raise IngestServiceError(
            f"repo returned snapshot_id {real_snapshot_id} != requested {snapshot_id}"
        )

    # 7 - live integrity check: recompute the receipt_hash from the bind
    # fields under the SAME snapshot_id and confirm it matches what we
    # signed. This catches any post-build mutation in the model layer.
    recomputed = recompute_receipt_hash(receipt, snapshot_id)
    integrity_ok = recomputed == receipt.receipt_hash

    return IngestResult(
        event_id=event.id,
        receipt_id=receipt.id,
        policy_snapshot_id=snapshot_id,
        receipt_hash=receipt.receipt_hash,
        integrity_ok=integrity_ok,
    )

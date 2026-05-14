"""POST /v1/events — full-stack ingest endpoint (CP9.11).

CP9.11 lands real persistence. Previously this endpoint validated the Event
schema and returned 202 Accepted with the event id but did NOT persist (the
review's biggest finding on this module: "the endpoint is a no-op
acknowledgement today").

Now the endpoint:

- Accepts the validated ``Event``.
- Resolves the active policy bundle for the tenant (via ``PolicyBundleProvider``).
- Evaluates the action against the enforcement gateway (via
  ``PolicyEnforcementClient``).
- Builds and signs a Receipt over the chain head + the new event.
- Atomically persists (snapshot, event, receipt) via
  ``write_event_with_receipt``.
- Returns 201 Created with the ``event_id``, ``receipt_id``,
  ``policy_snapshot_id``, ``receipt_hash``, and ``integrity_ok`` boolean.

Routing logic stays thin; the orchestration lives in
``apps.api.ingest_service.ingest_event``. The route's job is to:

- Hold the request body schema (``EventCreatedResponse``).
- Wire FastAPI ``Depends(...)`` for the four service inputs (session,
  enforcement client, bundle provider, signing key provider).
- Map ``IngestServiceError`` to HTTP 422 with a stable structured body so
  downstream callers can retry / inspect.

The four providers are module-level singletons by default so the same
in-memory caches (signing keys, bundles) are reused across requests in one
process. Tests override each via ``app.dependency_overrides`` for full
isolation.

Future-tracked items:
- Per-tenant auth & tenant-id-from-token (top-20 #1, CP10.1).
- Idempotency-Key header (NEW-P9.8.2): IMPLEMENTED in CP9.17. See
  ``apps.api.idempotency_store`` for the contract and storage impls.
- Payload size limit (NEW-P9.8.3).
- OTel traceparent propagation (CP12.1).
- Async-queue back-pressure (top-20 #8, CP12.4).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.idempotency_store import (
    IdempotencyKeyConflict,
    IdempotencyStore,
    InMemoryIdempotencyStore,
    compute_body_hash,
    is_valid_idempotency_key,
)
from apps.api.ingest_service import (
    AgentSigningKeyProvider,
    DefaultBundleProvider,
    IngestServiceError,
    InMemoryAgentSigningKeyProvider,
    InMemorySigningKeyProvider,
    PolicyBundleProvider,
    TenantSigningKeyProvider,
    ingest_event,
)
from apps.api.routes.receipts import get_session
from packages.policy.enforcement import PolicyEnforcementClient
from packages.policy.lobstertrap import MockLobsterTrapClient
from packages.schema.event import Event

router = APIRouter(prefix="/v1", tags=["events"])


# ---------------------------------------------------------------------------
# Module-level provider singletons (default impls for hackathon demo).
# Tests override via app.dependency_overrides.
# ---------------------------------------------------------------------------

_DEFAULT_BUNDLE_PROVIDER = DefaultBundleProvider()
_DEFAULT_SIGNING_KEY_PROVIDER = InMemorySigningKeyProvider()
_DEFAULT_AGENT_SIGNING_KEY_PROVIDER = InMemoryAgentSigningKeyProvider()
_DEFAULT_IDEMPOTENCY_STORE: IdempotencyStore = InMemoryIdempotencyStore()


async def get_bundle_provider() -> PolicyBundleProvider:
    """Default policy bundle provider. Override in tests."""
    return _DEFAULT_BUNDLE_PROVIDER


async def get_signing_key_provider() -> TenantSigningKeyProvider:
    """Default tenant signing key provider. Override in tests."""
    return _DEFAULT_SIGNING_KEY_PROVIDER


async def get_agent_signing_key_provider() -> AgentSigningKeyProvider:
    """Default agent signing key provider (CP9.18 / BR-02). Override in tests.

    Today this is the process-local in-memory impl. Production wiring uses
    the KMS adapter (CP11.1).
    """
    return _DEFAULT_AGENT_SIGNING_KEY_PROVIDER


async def get_idempotency_store() -> IdempotencyStore:
    """Default idempotency store. Override in tests.

    Today this is the process-local in-memory impl. Production wiring
    swaps in ``PostgresIdempotencyStore(session)`` constructed inside the
    request scope so the dedup record is written in the same transaction
    as the rest of the ingest pipeline (rolls back together on failure).
    """
    return _DEFAULT_IDEMPOTENCY_STORE


async def get_enforcement_client() -> PolicyEnforcementClient:
    """Default policy enforcement client.

    Returns a fresh ``MockLobsterTrapClient`` bound to the same bundle the
    default ``PolicyBundleProvider`` would return for a tenant. In a real
    deployment this is the live Veea HTTP client (NEW-P9.8.22).

    NOTE: this provider needs to know which bundle is active to issue
    verdicts that bind to it. For the demo we resolve through the
    default bundle provider directly. Tests override this entirely.
    """
    # Lazy-import the bundle provider's cache; uses bundle for the FIRST
    # tenant requested. In production each enforcement client call is its
    # own HTTP round-trip and the bundle is encoded in the trap config.
    # Returning a deterministic mock here is acceptable because the ingest
    # service then validates verdict.policy_bundle_id == active_bundle.id
    # and refuses on drift.
    return _DEFAULT_ENFORCEMENT_CLIENT


# We can't construct a MockLobsterTrapClient at module load because it needs
# a bundle_id. Construct it lazily on first use, bound to the first tenant's
# default bundle. For multi-tenant production this gets replaced entirely.
class _LazyDefaultEnforcement(PolicyEnforcementClient):
    """Bridges to the default bundle provider on first call.

    The instance is module-level and shared across requests. On each
    ``evaluate`` call it resolves the tenant's active bundle and lazily
    builds a per-tenant ``MockLobsterTrapClient`` cached under the bundle id.
    """

    def __init__(self) -> None:
        self._per_bundle: dict[UUID, MockLobsterTrapClient] = {}

    async def evaluate(self, tenant_id: UUID, action: dict[str, object]) -> object:  # type: ignore[override]
        bundle = await _DEFAULT_BUNDLE_PROVIDER.get_active_bundle(tenant_id)
        client = self._per_bundle.get(bundle.id)
        if client is None:
            client = MockLobsterTrapClient(
                policy_bundle_id=bundle.id,
                policy_bundle_version=bundle.version,
                content=bundle.content,
            )
            self._per_bundle[bundle.id] = client
        return await client.evaluate(tenant_id, action)


_DEFAULT_ENFORCEMENT_CLIENT: PolicyEnforcementClient = _LazyDefaultEnforcement()


# ---------------------------------------------------------------------------
# Wire form
# ---------------------------------------------------------------------------


class EventCreatedResponse(BaseModel):
    """Returned by POST /v1/events on successful persistence (CP9.11)."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(..., description="UUID of the persisted event")
    receipt_id: str = Field(..., description="UUID of the issued Receipt")
    policy_snapshot_id: str = Field(
        ..., description="UUID of the policy snapshot bound into the Receipt"
    )
    receipt_hash: str = Field(..., description="SHA-256 hex of the Receipt's canonical bind fields")
    integrity_ok: bool = Field(
        ...,
        description=(
            "True iff a live recompute of the receipt_hash from the persisted"
            " bind fields equals the stored receipt_hash."
        ),
    )
    status: str = Field(default="created")
    persisted_at: datetime = Field(..., description="Server-side acknowledgement timestamp")


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.post(
    "/events",
    status_code=status.HTTP_201_CREATED,
    response_model=EventCreatedResponse,
    summary="Submit a single agent event for evidence-grade ingestion (full persistence)",
    responses={
        201: {"description": "Event accepted, Receipt issued, chain extended"},
        400: {
            "description": (
                "Idempotency-Key header was supplied but failed the format contract"
                " (length 16-128, chars A-Za-z0-9_-)."
            )
        },
        409: {
            "description": (
                "Idempotency-Key was previously used for this tenant with a"
                " different request body within the TTL window."
            )
        },
        422: {"description": "Event failed schema validation OR policy enforcement failed"},
    },
)
async def submit_event(
    event: Event,
    response: Response,
    session: AsyncSession = Depends(get_session),  # noqa: B008
    enforcement_client: PolicyEnforcementClient = Depends(get_enforcement_client),  # noqa: B008
    bundle_provider: PolicyBundleProvider = Depends(get_bundle_provider),  # noqa: B008
    signing_key_provider: TenantSigningKeyProvider = Depends(  # noqa: B008
        get_signing_key_provider
    ),
    agent_signing_key_provider: AgentSigningKeyProvider = Depends(  # noqa: B008
        get_agent_signing_key_provider
    ),
    idempotency_store: IdempotencyStore = Depends(get_idempotency_store),  # noqa: B008
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> EventCreatedResponse:
    """Accept an Event, run ingest pipeline, return 201 with the issued Receipt.

    Idempotency contract: when the ``Idempotency-Key`` header is present,
    the body hash + key + tenant_id triple is used to dedup retries. Same
    triple within the TTL window -> the original response is returned
    unchanged. Same key + different body -> 409 Conflict. No header ->
    every request produces a new Event + Receipt (today's default).
    """
    # ---- Idempotency lookup (only when the header is present) ----
    body_hash: str | None = None
    if idempotency_key is not None:
        if not is_valid_idempotency_key(idempotency_key):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "idempotency_key_malformed",
                    "reason": ("Idempotency-Key must match ^[A-Za-z0-9_-]{16,128}$"),
                },
            )
        # Hash the *client-meaningful* subset of the parsed Event. We can't
        # use ``model_dump(exclude_defaults=True)`` because Pydantic v2 does
        # not treat ``default_factory``-produced values (Event.id is
        # ``default_factory=uuid4``) as "defaults" - the factory regenerates
        # a fresh UUID on every parse, and the dump always includes it. A
        # retry would then produce a different body_hash and trigger 409.
        #
        # The dedup contract is over the fields the client actually sends.
        # The Event.id is server-generated when absent from the wire body
        # and the client's retry wouldn't preserve it across calls anyway.
        # exclude={'id'} excludes it; exclude_none + exclude_defaults handles
        # the remaining optionals + the payload={} default.
        body_hash = compute_body_hash(
            event.model_dump(
                mode="json",
                exclude={"id"},
                exclude_defaults=True,
                exclude_none=True,
            )
        )
        try:
            cached = await idempotency_store.lookup_or_claim(
                tenant_id=event.tenant_id,
                key=idempotency_key,
                body_hash=body_hash,
            )
        except IdempotencyKeyConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "idempotency_key_conflict",
                    "reason": str(exc),
                },
            ) from exc
        if cached is not None:
            cached_body = cached.response_body
            response.headers["X-Forensa-Event-Id"] = str(cached_body["event_id"])
            response.headers["X-Forensa-Receipt-Id"] = str(cached_body["receipt_id"])
            response.headers["Idempotent-Replayed"] = "true"
            return EventCreatedResponse(**cached_body)

    # ---- Fresh ingest path ----
    try:
        result = await ingest_event(
            session=session,
            event=event,
            enforcement_client=enforcement_client,
            bundle_provider=bundle_provider,
            signing_key_provider=signing_key_provider,
            agent_signing_key_provider=agent_signing_key_provider,
        )
    except IngestServiceError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "ingest_failed",
                "reason": str(exc),
            },
        ) from exc

    persisted_at = datetime.now(UTC)
    response_body = EventCreatedResponse(
        event_id=str(result.event_id),
        receipt_id=str(result.receipt_id),
        policy_snapshot_id=str(result.policy_snapshot_id),
        receipt_hash=result.receipt_hash,
        integrity_ok=result.integrity_ok,
        persisted_at=persisted_at,
    )

    # Store the response under the Idempotency-Key so future retries
    # within the TTL window collapse to this one.
    if idempotency_key is not None and body_hash is not None:
        await idempotency_store.store(
            tenant_id=event.tenant_id,
            key=idempotency_key,
            body_hash=body_hash,
            response_status=201,
            response_body=response_body.model_dump(mode="json"),
        )

    response.headers["X-Forensa-Event-Id"] = str(result.event_id)
    response.headers["X-Forensa-Receipt-Id"] = str(result.receipt_id)
    return response_body

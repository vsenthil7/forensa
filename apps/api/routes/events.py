"""POST /v1/events — validate-and-acknowledge ingest endpoint.

Phase 1 (this unit): validates incoming events against the Event Pydantic
schema and returns 202 Accepted with the event id. No DB persistence yet —
that lands in Unit 8 with the normaliser + ingest pipeline.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, ConfigDict, Field

from packages.schema.event import Event

router = APIRouter(prefix="/v1", tags=["events"])


class EventAcceptedResponse(BaseModel):
    """Returned by POST /v1/events on successful validation."""
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(..., description="UUID of the accepted event")
    status: str = Field(default="accepted")
    accepted_at: datetime = Field(..., description="Server-side acknowledgement timestamp")


@router.post(
    "/events",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=EventAcceptedResponse,
    summary="Submit a single agent event for evidence-grade ingestion",
)
async def submit_event(event: Event, response: Response) -> EventAcceptedResponse:
    """Accept a validated Event and return 202 with the event id.

    Returns 422 (FastAPI default) on schema validation failure. Persistence
    happens asynchronously downstream; clients receive immediate ack with
    the event id they can use to query receipts later.
    """
    response.headers["X-Forensa-Event-Id"] = str(event.id)
    return EventAcceptedResponse(
        event_id=str(event.id),
        accepted_at=datetime.now(timezone.utc),
    )


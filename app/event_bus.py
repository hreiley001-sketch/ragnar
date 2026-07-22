"""BirdmanOS event bus.

Every meaningful thing emits an event: user_joined_ride, bid_placed,
ride_phase_changed, payment_due, payment_captured, ride_complete, ride_tuned, stream_error…
Events are persisted (so the Command Hub can read them) and mirrored to the
'analytics observatory' (PostHog) when configured.
"""
from __future__ import annotations

import logging

import httpx
from sqlmodel import Session

from .config import settings
from .models import RideEvent

logger = logging.getLogger("ragnar.events")


def emit(session: Session, event_type: str, data: dict | None = None, ride_id: int | None = None) -> RideEvent:
    ev = RideEvent(ride_id=ride_id, type=event_type, data=data or {})
    session.add(ev)
    session.commit()
    session.refresh(ev)
    payload = {**(data or {}), "ride_id": ride_id, "event_type": event_type}
    _to_posthog(event_type, data or {}, ride_id)
    _to_platform_queue(event_type, payload, ride_id)
    return ev


def _to_platform_queue(event_type: str, payload: dict, ride_id: int | None) -> None:
    """Cross the async boundary — never wait on n8n.

    Maps ride lifecycle events onto modular workflow topics.
    """
    try:
        from .platform.queue import enqueue

        topic = event_type if "." in event_type else f"ride.{event_type}"
        workflow = None
        if "phase" in event_type:
            workflow = "ride/phase-changed"
            topic = "ride.phase_changed"
        enqueue(topic, payload, workflow=workflow)
    except Exception as exc:  # noqa: BLE001 - automation must never break a ride
        logger.warning("platform enqueue failed: %s", exc)


def _to_posthog(event_type: str, data: dict, ride_id: int | None) -> None:
    if not settings.posthog_api_key:
        return
    try:
        distinct = str(data.get("bidder") or data.get("user") or (f"ride_{ride_id}" if ride_id else "system"))
        with httpx.Client(timeout=4.0) as client:
            client.post(
                f"{settings.posthog_host}/capture/",
                json={
                    "api_key": settings.posthog_api_key,
                    "event": event_type,
                    "distinct_id": distinct,
                    "properties": {**data, "ride_id": ride_id, "$lib": "ragnar-birdmanos"},
                },
            )
    except Exception as exc:  # noqa: BLE001 - analytics must never break a ride
        logger.warning("PostHog emit failed: %s", exc)

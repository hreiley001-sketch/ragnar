"""BirdmanOS event bus.

Every meaningful thing emits an event: user_joined_ride, bid_placed,
ride_phase_changed, payment_due, payment_captured, ride_complete, ride_tuned, stream_error…
Events are persisted (so the Command Hub can read them) and mirrored to the
'analytics observatory' (PostHog) when configured.
"""
from __future__ import annotations

import logging
import threading

from sqlmodel import Session

from .config import settings
from .http_client import sync_client
from .models import RideEvent

logger = logging.getLogger("ragnar.events")


def emit(
    session: Session,
    event_type: str,
    data: dict | None = None,
    ride_id: int | None = None,
    *,
    commit: bool = True,
) -> RideEvent:
    """Persist an event.

    ``commit=True`` (default) matches historical callers that rely on emit to
    flush the transaction. Pass ``commit=False`` to flush only and let the
    caller own a single outer commit.
    """
    payload = data or {}
    ev = RideEvent(ride_id=ride_id, type=event_type, data=payload)
    session.add(ev)
    if commit:
        session.commit()
        session.refresh(ev)
    else:
        session.flush()
    _to_posthog_async(event_type, payload, ride_id)
    return ev


def _to_posthog_async(event_type: str, data: dict, ride_id: int | None) -> None:
    if not settings.posthog_api_key:
        return
    threading.Thread(
        target=_to_posthog,
        args=(event_type, data, ride_id),
        daemon=True,
        name="ragnar-posthog",
    ).start()


def _to_posthog(event_type: str, data: dict, ride_id: int | None) -> None:
    if not settings.posthog_api_key:
        return
    try:
        distinct = str(
            data.get("bidder")
            or data.get("user")
            or (f"ride_{ride_id}" if ride_id else "system")
        )
        sync_client(timeout=4.0).post(
            f"{settings.posthog_host}/capture/",
            json={
                "api_key": settings.posthog_api_key,
                "event": event_type,
                "distinct_id": distinct,
                "properties": {**data, "ride_id": ride_id, "$lib": "ragnar-birdmanos"},
            },
            timeout=4.0,
        )
    except Exception as exc:  # noqa: BLE001 - analytics must never break a ride
        logger.warning("PostHog emit failed: %s", exc)

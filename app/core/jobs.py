"""Birdman job envelope — FastAPI → Redis → n8n.

Standard payload shape. FastAPI never waits on n8n.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .queue import enqueue

# type → n8n webhook path (under N8N_WEBHOOK_BASE)
WORKFLOW_PATHS: dict[str, str] = {
    "notification": "notification/send",
    "enrich_content": "enrich/content",
    "user_event": "enrich/user-event",
    "aggregate_actions": "analytics/aggregate",
    "broadcast_event": "realtime/broadcast",
    "maintenance": "maintenance/run",
    "user_action": "actions/user-action",
    "user_action_like": "actions/user-like",
    # marketplace
    "listing_created": "market/listing-created",
    "order_placed": "market/order-placed",
    "order_status_changed": "market/order-status-changed",
    "seller_notification": "market/seller-notification",
    "buyer_notification": "market/buyer-notification",
    "market_daily_analytics": "market/daily-analytics",
    # legacy / product topics
    "ops.notify": "ops/notify",
    "media.enhance": "media/enhance",
    "ride.phase_changed": "ride/phase-changed",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def workflow_for(job_type: str, override: str | None = None) -> str:
    if override:
        return override
    if job_type in WORKFLOW_PATHS:
        return WORKFLOW_PATHS[job_type]
    return job_type.replace(".", "/").replace("_", "-")


def enqueue_job(
    job_type: str,
    *,
    user_id: str | None = None,
    content_id: str | None = None,
    action_type: str | None = None,
    extra: dict[str, Any] | None = None,
    workflow: str | None = None,
) -> dict[str, Any]:
    """Push a Birdman job. Returns queue metadata immediately."""
    payload: dict[str, Any] = {
        "type": job_type,
        "timestamp": utc_now_iso(),
    }
    if user_id is not None:
        payload["user_id"] = user_id
    if content_id is not None:
        payload["content_id"] = content_id
    if action_type is not None:
        payload["action_type"] = action_type
    if extra:
        payload.update(extra)

    path = workflow_for(job_type, workflow)
    return enqueue(job_type, payload, workflow=path)

"""Writes + n8n triggers — async boundary (Birdman muscles).

FastAPI writes intent, enqueues job, returns. n8n does the heavy work.
"""
from __future__ import annotations

from typing import Any, Optional

from app.core.jobs import enqueue_job
from app.models import ActionRequest, ActionResult
from app.utils.validators import require_non_empty


def enqueue_action(req: ActionRequest) -> ActionResult:
    """Generic enqueue — topic becomes job type."""
    topic = require_non_empty(req.topic, "topic")
    job = enqueue_job(
        topic,
        user_id=_as_str(req.payload.get("user_id")),
        content_id=_as_str(req.payload.get("content_id")),
        action_type=_as_str(req.payload.get("action_type")),
        extra={k: v for k, v in req.payload.items() if k not in {"user_id", "content_id", "action_type"}},
        workflow=req.workflow,
    )
    return _result(job)


def enqueue_user_action(
    *,
    user_id: str,
    action_type: str,
    content_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> ActionResult:
    """Core pattern: user did something → Redis → n8n."""
    job_type = "user_action_like" if action_type == "like" else "user_action"
    job = enqueue_job(
        job_type,
        user_id=user_id,
        content_id=content_id,
        action_type=action_type,
        extra=payload or {},
    )
    return _result(job)


def enqueue_notification(
    *,
    user_id: str,
    message: str,
    extra: dict[str, Any] | None = None,
) -> ActionResult:
    job = enqueue_job(
        "notification",
        user_id=user_id,
        extra={"message": message, **(extra or {})},
    )
    return _result(job)


def enqueue_broadcast(
    *,
    channel: str,
    event_type: str,
    data: dict[str, Any] | None = None,
) -> ActionResult:
    job = enqueue_job(
        "broadcast_event",
        extra={"channel": channel, "event_type": event_type, "data": data or {}},
    )
    return _result(job)


def enqueue_enrich_content(*, content_id: str, extra: dict[str, Any] | None = None) -> ActionResult:
    job = enqueue_job("enrich_content", content_id=content_id, extra=extra or {})
    return _result(job)


def _result(job: dict[str, Any]) -> ActionResult:
    return ActionResult(
        ok=True,
        job_id=job["id"],
        topic=job["topic"],
        workflow=job["workflow"],
        queued=True,
    )


def _as_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)

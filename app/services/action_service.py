"""Writes + n8n triggers — async boundary lives here."""
from __future__ import annotations

from app.core.queue import enqueue
from app.models import ActionRequest, ActionResult
from app.utils.validators import require_non_empty


def enqueue_action(req: ActionRequest) -> ActionResult:
    topic = require_non_empty(req.topic, "topic")
    job = enqueue(topic, req.payload, workflow=req.workflow)
    return ActionResult(
        ok=True,
        job_id=job["id"],
        topic=job["topic"],
        workflow=job["workflow"],
        queued=True,
    )

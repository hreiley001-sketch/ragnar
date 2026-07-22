"""Redis queue — FastAPI → n8n pipeline (never wait on n8n in the hot path)."""
from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections import deque
from typing import Any

from .cache import get_redis
from .config import settings

logger = logging.getLogger("ragnar.core.queue")

QUEUE_KEY = "birdman:queue:jobs"
_local: deque[dict[str, Any]] = deque()
_local_lock = threading.Lock()


def enqueue(
    topic: str,
    payload: dict[str, Any] | None = None,
    *,
    workflow: str | None = None,
) -> dict[str, Any]:
    """Enqueue a background job. Returns metadata immediately."""
    job = {
        "id": uuid.uuid4().hex,
        "topic": topic,
        "workflow": workflow or topic.replace(".", "/"),
        "payload": payload or {},
        "enqueued_at": time.time(),
    }
    r = get_redis()
    if r is not None:
        try:
            r.rpush(QUEUE_KEY, json.dumps(job, default=str))
            logger.debug("enqueued %s → redis %s", topic, job["id"])
            if settings.n8n_webhook_base:
                _spawn_n8n_fire(job)
            return job
        except Exception as exc:  # noqa: BLE001
            logger.warning("redis enqueue failed, using local: %s", exc)

    with _local_lock:
        _local.append(job)
    logger.debug("enqueued %s → local %s", topic, job["id"])

    if settings.n8n_webhook_base:
        _spawn_n8n_fire(job)
    return job


def dequeue(timeout_seconds: float = 0) -> dict[str, Any] | None:
    r = get_redis()
    if r is not None:
        try:
            if timeout_seconds > 0:
                item = r.blpop(QUEUE_KEY, timeout=max(1, int(timeout_seconds)))
                if not item:
                    return None
                return json.loads(item[1])
            raw = r.lpop(QUEUE_KEY)
            return json.loads(raw) if raw else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("redis dequeue failed: %s", exc)

    with _local_lock:
        if _local:
            return _local.popleft()
    return None


def queue_depth() -> dict[str, Any]:
    r = get_redis()
    if r is not None:
        try:
            return {"backend": "redis", "depth": int(r.llen(QUEUE_KEY))}
        except Exception as exc:  # noqa: BLE001
            return {"backend": "redis", "depth": None, "error": str(exc)}
    with _local_lock:
        return {"backend": "local", "depth": len(_local)}


def _spawn_n8n_fire(job: dict[str, Any]) -> None:
    def _run() -> None:
        try:
            _trigger_n8n(job["workflow"], job)
        except Exception as exc:  # noqa: BLE001
            logger.warning("n8n fire failed for %s: %s", job.get("id"), exc)

    threading.Thread(target=_run, name=f"n8n-{job['id'][:8]}", daemon=True).start()


def _trigger_n8n(workflow: str, body: dict[str, Any]) -> dict[str, Any]:
    import httpx

    base = settings.n8n_webhook_base.rstrip("/")
    if not base:
        return {"ok": False, "skipped": True, "reason": "n8n_webhook_base unset"}

    url = f"{base}/{workflow.lstrip('/')}"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.n8n_shared_secret:
        headers["X-Birdman-Token"] = settings.n8n_shared_secret

    try:
        with httpx.Client(timeout=settings.n8n_timeout_seconds) as client:
            resp = client.post(url, json=body or {}, headers=headers)
        ok = 200 <= resp.status_code < 300
        if not ok:
            logger.warning("n8n %s → %s %s", workflow, resp.status_code, resp.text[:200])
        return {"ok": ok, "status_code": resp.status_code, "workflow": workflow, "url": url}
    except Exception as exc:  # noqa: BLE001
        logger.warning("n8n trigger failed %s: %s", workflow, exc)
        return {"ok": False, "workflow": workflow, "error": str(exc)}


def n8n_status() -> dict[str, Any]:
    return {
        "enabled": bool(settings.n8n_webhook_base),
        "base": settings.n8n_webhook_base or None,
        "timeout_seconds": settings.n8n_timeout_seconds,
    }

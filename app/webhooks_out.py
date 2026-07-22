"""Async outbound bridge to n8n — never blocks the request hot path.

Architecture rule: FastAPI must not wait for n8n to finish a workflow.
All delivery is fire-and-forget via:
  1. Redis list queue (preferred when REDIS_URL is set), drained by a worker, or
  2. asyncio.create_task / BackgroundTasks HTTP POST (dev / single-node).

Synchronous HTTP from a request handler is forbidden.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from .config import settings

logger = logging.getLogger("ragnar.webhooks_out")

QUEUE_KEY = "ragnar:n8n:queue"


def n8n_configured() -> bool:
    return bool(settings.n8n_webhook_url)


def _sign(body: bytes) -> str | None:
    secret = settings.n8n_webhook_secret
    if not secret:
        return None
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _payload(event: str, data: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "event": event,
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": "ragnar",
        "data": data or {},
    }


def _redis_client():
    url = (settings.redis_url or "").strip()
    if not url:
        return None
    try:
        import redis

        return redis.Redis.from_url(url, decode_responses=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("n8n queue redis unavailable: %s", exc)
        return None


async def _post_webhook(event: str, data: dict[str, Any] | None) -> bool:
    """Perform the HTTP POST. Called only from background tasks / workers."""
    if not n8n_configured():
        return False
    payload = _payload(event, data)
    body = json.dumps(payload, default=str).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "RAGNAR-webhooks/1.0",
        "X-Ragnar-Event": event,
    }
    sig = _sign(body)
    if sig:
        headers["X-Ragnar-Signature"] = sig
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            r = await client.post(settings.n8n_webhook_url, content=body, headers=headers)
        if r.status_code >= 400:
            logger.warning("n8n webhook %s failed %s: %s", event, r.status_code, r.text[:200])
            return False
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("n8n webhook error (%s): %s", event, exc)
        return False


def _schedule_http(event: str, data: dict[str, Any] | None) -> None:
    """Fire-and-forget HTTP without blocking the caller."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop (sync worker / test) — spawn a short-lived one.
        try:
            asyncio.run(_post_webhook(event, data))
        except Exception as exc:  # noqa: BLE001
            logger.warning("n8n sync-fallback failed (%s): %s", event, exc)
        return

    task = loop.create_task(_post_webhook(event, data))

    def _done(t: asyncio.Task) -> None:
        try:
            t.result()
        except Exception as exc:  # noqa: BLE001
            logger.warning("n8n background task failed (%s): %s", event, exc)

    task.add_done_callback(_done)


def enqueue(event: str, data: dict[str, Any] | None = None) -> bool:
    """Queue an n8n event and return immediately.

    Prefer Redis LPUSH when available; otherwise schedule async HTTP.
    Returns True if the event was accepted for delivery (not that n8n finished).
    """
    if not n8n_configured():
        return False
    payload = _payload(event, data)
    client = _redis_client()
    if client is not None:
        try:
            client.lpush(QUEUE_KEY, json.dumps(payload, default=str))
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("n8n enqueue redis failed, falling back to HTTP task: %s", exc)
    _schedule_http(event, data)
    return True


# Back-compat name used by older call sites / tests. Prefer ``enqueue``.
def dispatch(event: str, data: dict[str, Any] | None = None) -> bool:
    """Alias for ``enqueue`` — never waits for n8n to finish."""
    return enqueue(event, data)


async def drain_once(limit: int = 20) -> int:
    """Worker helper: pop up to ``limit`` queued events and POST them.

    Safe to run from a cron, Render background worker, or n8n itself polling Redis.
    """
    client = _redis_client()
    if client is None:
        return 0
    sent = 0
    for _ in range(max(1, limit)):
        raw = client.rpop(QUEUE_KEY)
        if not raw:
            break
        try:
            item = json.loads(raw)
            ok = await _post_webhook(item.get("event") or "unknown", item.get("data") or {})
            if ok:
                sent += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("n8n drain item failed: %s", exc)
    return sent

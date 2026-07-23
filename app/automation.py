"""n8n automation bridge — emit domain events to an n8n webhook.

Key-gated and safe by design:
  * If N8N_WEBHOOK_BASE is unset, emit() is a no-op (returns immediately).
  * Fire-and-forget: failures are swallowed and logged, never raised into the
    request path. Automation must never take down a checkout or a sign-up.

n8n then orchestrates the side effects (emails, Slack/Discord pings, CRM,
follow-up sequences) as visual workflows — see
vault/Ragnarips/Automation/README.md.

Usage (from a router/service):
    from ..automation import emit
    await emit("order.paid", {"order_id": order.id, "total_cents": total})
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging

import httpx

from .config import settings

logger = logging.getLogger("ragnar.automation")

# Known event names (documentation + typo guard). Extend as workflows are added.
EVENTS = {
    "seller.applied",
    "seller.founding_claimed",
    "listing.created",
    "listing.sold",
    "order.paid",
    "order.shipped",
    "dispute.opened",
    "stream.started",
}


def _sign(body: bytes) -> str:
    return hmac.new(settings.n8n_webhook_secret.encode(), body, hashlib.sha256).hexdigest()


async def emit(event: str, payload: dict, *, timeout: float = 3.0) -> bool:
    """POST an event to n8n. Returns True if delivered, False otherwise.

    Never raises — automation is best-effort and must not break callers.
    """
    if not settings.automation_enabled:
        return False
    if event not in EVENTS:
        logger.warning("automation: unknown event %r (sending anyway)", event)

    url = f"{settings.n8n_webhook_base}/{event}"
    body = json.dumps({"event": event, "data": payload}).encode()
    headers = {"Content-Type": "application/json"}
    if settings.n8n_webhook_secret:
        headers["X-Ragnar-Signature"] = _sign(body)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, content=body, headers=headers)
            resp.raise_for_status()
        return True
    except Exception:  # noqa: BLE001 — best-effort; log and move on
        logger.exception("automation: failed to emit %s", event)
        return False

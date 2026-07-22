"""Outbound webhooks for automation hubs (n8n, Make, Zapier).

Key-gated via ``N8N_WEBHOOK_URL``. Fail-soft — never break the action that
triggered the event. Payload shape is n8n-friendly JSON.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from .config import settings

logger = logging.getLogger("ragnar.webhooks_out")


def n8n_configured() -> bool:
    return bool(settings.n8n_webhook_url)


def _sign(body: bytes) -> str | None:
    secret = settings.n8n_webhook_secret
    if not secret:
        return None
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def dispatch(event: str, data: dict[str, Any] | None = None) -> bool:
    """POST ``{event, ts, source, data}`` to the configured n8n webhook.

    Returns True on HTTP < 400. No-op (False) when unset or on any failure.
    """
    if not n8n_configured():
        return False
    payload = {
        "event": event,
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": "ragnar",
        "data": data or {},
    }
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
        with httpx.Client(timeout=12.0) as client:
            r = client.post(settings.n8n_webhook_url, content=body, headers=headers)
        if r.status_code >= 400:
            logger.warning("n8n webhook %s failed %s: %s", event, r.status_code, r.text[:200])
            return False
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("n8n webhook error (%s): %s", event, exc)
        return False

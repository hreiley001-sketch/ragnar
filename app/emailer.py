"""Outbound alerts: Resend email + Discord webhook. Both key-gated; both
fail-soft (an alert must never break the action that triggered it).
"""
from __future__ import annotations

import logging

import httpx

from .config import settings

logger = logging.getLogger("ragnar.emailer")


def email_configured() -> bool:
    return bool(settings.resend_api_key)


def discord_configured() -> bool:
    return bool(settings.discord_webhook_url)


def send_email(to: str | list[str], subject: str, html: str) -> bool:
    """Send via Resend (https://resend.com). Requires a verified sending domain."""
    if not email_configured() or not to:
        return False
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": settings.email_from,
                    "to": [to] if isinstance(to, str) else to,
                    "subject": subject[:200],
                    "html": html,
                },
            )
        if r.status_code >= 400:
            logger.warning("Resend failed %s: %s", r.status_code, r.text[:200])
            return False
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Resend error: %s", exc)
        return False


def discord_alert(message: str) -> bool:
    """Ping the ops Discord channel (great for founding applications & orders)."""
    if not discord_configured():
        return False
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(settings.discord_webhook_url, json={"content": message[:1900]})
        return r.status_code < 400
    except Exception as exc:  # noqa: BLE001
        logger.warning("Discord webhook error: %s", exc)
        return False


def ops_alert(subject: str, body: str = "") -> None:
    """Best-effort alert to the admin emails + Discord ops channel."""
    if settings.admin_emails:
        send_email(settings.admin_emails, subject, f"<p>{body or subject}</p>")
    discord_alert(f"**{subject}**\n{body}" if body else f"**{subject}**")

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


def _brand_wrap(inner: str) -> str:
    return (
        '<div style="font-family:system-ui,Segoe UI,sans-serif;background:#0b1220;'
        'color:#dfe8f2;padding:32px;border-radius:14px;max-width:520px;margin:0 auto;">'
        '<h1 style="letter-spacing:.3em;color:#eaf3fb;margin:0 0 4px;">RAGNAR</h1>'
        '<p style="color:#6c8199;font-size:12px;letter-spacing:.14em;text-transform:uppercase;'
        'margin:0 0 22px;">ᚱᚨᚷᚾᚨᚱ · trading-card marketplace</p>'
        f'{inner}'
        '<p style="color:#6c8199;font-size:12px;margin-top:26px;">Guided by counsel, driven by conquest.</p>'
        '</div>'
    )


def send_verification_email(to: str, name: str, link: str, *, is_staff_domain: bool = False) -> bool:
    """Send the account verification email. Returns False if email isn't configured."""
    greeting = f"Hi {name}," if name else "Welcome,"
    perk = (
        '<p style="color:#f0c674;">Because you\'re on the ragnarips.com team, verifying also '
        'unlocks the <strong>Command Hub</strong>.</p>' if is_staff_domain else ''
    )
    inner = (
        f'<p>{greeting}</p>'
        '<p>Confirm your email to activate your RAGNAR account.</p>'
        f'{perk}'
        f'<p style="margin:24px 0;"><a href="{link}" '
        'style="background:#2a8fc4;color:#f2fbff;text-decoration:none;padding:12px 22px;'
        'border-radius:10px;font-weight:600;display:inline-block;">Verify my email</a></p>'
        f'<p style="color:#9fb2c6;font-size:13px;">Or paste this link:<br>'
        f'<a href="{link}" style="color:#6fd6ff;">{link}</a></p>'
        '<p style="color:#6c8199;font-size:12px;">If you didn\'t create this account, ignore this email.</p>'
    )
    return send_email(to, "Verify your RAGNAR account", _brand_wrap(inner))


def send_password_reset_email(to: str, name: str, link: str) -> bool:
    greeting = f"Hi {name}," if name else "Hi,"
    inner = (
        f'<p>{greeting}</p>'
        '<p>We received a request to reset your RAGNAR password.</p>'
        f'<p style="margin:24px 0;"><a href="{link}" '
        'style="background:#2a8fc4;color:#f2fbff;text-decoration:none;padding:12px 22px;'
        'border-radius:10px;font-weight:600;display:inline-block;">Reset password</a></p>'
        f'<p style="color:#9fb2c6;font-size:13px;">Or paste this link:<br>'
        f'<a href="{link}" style="color:#6fd6ff;">{link}</a></p>'
        '<p style="color:#6c8199;font-size:12px;">This link expires in 1 hour. '
        "If you didn't request a reset, you can ignore this email.</p>"
    )
    return send_email(to, "Reset your RAGNAR password", _brand_wrap(inner))


def ops_alert(subject: str, body: str = "") -> None:
    """Best-effort alert to the admin emails + Discord ops channel."""
    if settings.admin_emails:
        send_email(settings.admin_emails, subject, f"<p>{body or subject}</p>")
    discord_alert(f"**{subject}**\n{body}" if body else f"**{subject}**")

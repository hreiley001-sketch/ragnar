"""Payments bridge for support refunds — thin wrapper over ``payments.create_refund``."""
from __future__ import annotations

from typing import Any

from ..models import Order
from .. import payments


def try_refund(order: Order, amount_cents: int, *, reason: str = "") -> dict[str, Any]:
    """Attempt a real Stripe refund when the order was paid via Checkout.

    Non-Stripe / unconfigured cases return ``ok=False`` with an explicit reason
    so callers do not pretend money moved.
    """
    if not payments.configured():
        return {
            "ok": False,
            "pending": False,
            "reason": "Stripe not configured — cannot move money.",
        }
    if not order.stripe_session_id:
        return {
            "ok": False,
            "pending": False,
            "reason": "No Stripe session on order — offline/manual sale has no card charge to refund.",
        }
    result = payments.create_refund(order, amount_cents, reason=reason)
    if result.get("ok") and payments.stripe_refund_status_ok(result.get("status")):
        return {
            "ok": True,
            "refund_id": result.get("refund_id"),
            "status": result.get("status"),
            "amount_cents": result.get("amount_cents", amount_cents),
        }
    return {
        "ok": False,
        "pending": False,
        "reason": result.get("reason") or f"Stripe refund status={result.get('status')}",
    }

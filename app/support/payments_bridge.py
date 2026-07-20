"""Payments bridge for support refunds.

Attempts a real Stripe refund when configured and the order has a Checkout
session; otherwise records a ledger-only refund so the workflow still completes.
"""
from __future__ import annotations

import logging
from typing import Any

from ..models import Order
from .. import payments

logger = logging.getLogger("ragnar.support.payments")


def try_refund(order: Order, amount_cents: int, *, reason: str = "") -> dict[str, Any]:
    if not payments.configured():
        return {
            "ok": False,
            "pending": True,
            "reason": "Stripe not configured — refund recorded in Support OS ledger.",
        }
    if not order.stripe_session_id:
        return {
            "ok": False,
            "pending": True,
            "reason": "No Stripe session on order — ledger refund only.",
        }
    try:
        stripe = payments._stripe()  # noqa: SLF001
        session_obj = stripe.checkout.Session.retrieve(order.stripe_session_id)
        pi = session_obj.get("payment_intent")
        if not pi:
            return {
                "ok": False,
                "pending": True,
                "reason": "Checkout session has no payment_intent yet.",
            }
        refund = stripe.Refund.create(
            payment_intent=pi if isinstance(pi, str) else pi.get("id", pi),
            amount=amount_cents,
            reason="requested_by_customer",
            metadata={
                "ragnar_order_id": str(order.id),
                "support_reason": (reason or "")[:100],
            },
        )
        return {"ok": True, "refund_id": refund.id, "status": refund.status}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Stripe refund failed for order %s: %s", order.id, exc)
        return {
            "ok": False,
            "pending": True,
            "reason": f"Stripe refund error: {exc}",
        }

"""Action execution — tools the AI can call (orders, refunds, labels, notify)."""
from __future__ import annotations

import logging
import secrets
from typing import Optional

from sqlmodel import Session, select

from ..models import (
    Dispute,
    Order,
    OrderStatus,
    Seller,
    SupportConversation,
    SupportRefund,
    utcnow,
)
from ..notify import notify, notify_admins, notify_seller
from ..shipping import tracking_url
from . import payments_bridge

logger = logging.getLogger("ragnar.support.actions")


def get_buyer_order(
    session: Session,
    order_id: int,
    *,
    user_id: Optional[int],
    staff: bool = False,
) -> Optional[Order]:
    order = session.get(Order, order_id)
    if not order:
        return None
    if staff:
        return order
    if user_id and order.buyer_user_id == user_id:
        return order
    # Allow lookup by email match is intentionally not done here — auth required.
    return None


def list_buyer_orders(session: Session, user_id: int, *, limit: int = 10) -> list[Order]:
    return list(session.exec(
        select(Order)
        .where(Order.buyer_user_id == user_id)
        .order_by(Order.created_at.desc())
        .limit(limit)
    ).all())


def order_summary(session: Session, order: Order) -> dict:
    seller = session.get(Seller, order.seller_id) if order.seller_id else None
    return {
        "id": order.id,
        "title": order.title,
        "status": order.status,
        "price": round(order.price_cents / 100, 2),
        "shipping": round((order.shipping_cents or 0) / 100, 2),
        "total": round((order.price_cents + (order.shipping_cents or 0)) / 100, 2),
        "tracking_number": order.tracking_number,
        "carrier": order.carrier,
        "tracking_url": tracking_url(order.carrier, order.tracking_number),
        "seller_handle": seller.handle if seller else None,
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }


def cancel_order(session: Session, order: Order) -> Order:
    order.status = OrderStatus.cancelled.value
    order.updated_at = utcnow()
    session.add(order)
    session.commit()
    session.refresh(order)
    return order


def issue_refund(
    session: Session,
    order: Order,
    *,
    amount_cents: int,
    reason: str,
    conversation: Optional[SupportConversation] = None,
    issued_by: str = "ai",
    kind: str = "full",
    require_stripe: bool | None = None,
) -> dict:
    """Issue a refund. Stripe-paid orders must succeed in Stripe before local status updates.

    Offline/manual orders (no ``stripe_session_id``) may be cancelled locally with
    status ``cancelled`` and SupportRefund status ``ledger_cancelled`` — never
    labeled as a Stripe refund.
    """
    total = order.price_cents + (order.shipping_cents or 0)
    amount_cents = max(0, min(amount_cents, total))
    kind = "partial" if amount_cents < total else kind
    already = int(getattr(order, "refunded_cents", 0) or 0)
    if already + amount_cents > total:
        amount_cents = max(0, total - already)

    has_stripe = bool(order.stripe_session_id)
    if require_stripe is None:
        require_stripe = has_stripe

    stripe_id = None
    status = "recorded"
    stripe_result: dict = {"ok": False}

    if has_stripe:
        stripe_result = payments_bridge.try_refund(order, amount_cents, reason=reason)
        if not stripe_result.get("ok"):
            return {
                "ok": False,
                "error": stripe_result.get("reason") or "Stripe refund failed",
                "status": "failed",
                "amount_cents": amount_cents,
                "amount": round(amount_cents / 100, 2),
                "stripe": stripe_result,
                "order_status": order.status,
            }
        status = "stripe_refunded" if stripe_result.get("status") == "succeeded" else "stripe_pending"
        if status == "stripe_pending" and stripe_result.get("status") == "pending":
            status = "stripe_refunded"  # pending is accepted as in-flight success
        stripe_id = stripe_result.get("refund_id")
        order.stripe_refund_id = stripe_id
        order.refunded_cents = already + amount_cents
        if kind == "full" or order.refunded_cents >= total:
            order.status = OrderStatus.refunded.value
    else:
        if require_stripe:
            return {
                "ok": False,
                "error": "Order was not paid through Stripe — cannot issue a card refund.",
                "status": "failed",
                "amount_cents": amount_cents,
                "amount": round(amount_cents / 100, 2),
                "order_status": order.status,
            }
        # Manual/offline: cancel locally; do not claim a card refund.
        status = "ledger_cancelled"
        order.refunded_cents = already + amount_cents
        if kind == "full" or order.refunded_cents >= total:
            order.status = OrderStatus.cancelled.value

    row = SupportRefund(
        order_id=order.id,
        conversation_id=conversation.id if conversation else None,
        amount_cents=amount_cents,
        kind=kind,
        status=status,
        stripe_refund_id=stripe_id,
        reason=(reason or "")[:500] or None,
        issued_by=issued_by,
    )
    session.add(row)
    order.updated_at = utcnow()
    session.add(order)
    session.commit()
    session.refresh(row)
    session.refresh(order)

    label = (
        f"${amount_cents/100:.2f} refunded via Stripe."
        if status.startswith("stripe")
        else f"${amount_cents/100:.2f} order cancelled (no card charge)."
    )
    if order.buyer_user_id:
        notify(
            session, order.buyer_user_id, "refund_issued",
            f"Refund — {order.title}",
            body=label,
            link="/account#orders",
        )
    seller = session.get(Seller, order.seller_id) if order.seller_id else None
    notify_seller(
        session, seller, "refund_issued",
        f"Refund on order #{order.id}",
        body=f"{label} — {reason[:120] if reason else 'support'}",
        link="/account#orders",
    )
    return {
        "ok": True,
        "refund_id": row.id,
        "amount_cents": amount_cents,
        "amount": round(amount_cents / 100, 2),
        "status": status,
        "stripe_refund_id": stripe_id,
        "order_status": order.status,
        "stripe": stripe_result,
    }


def create_return_label(session: Session, order: Order) -> dict:
    """Generate a mock/prepaid return label reference (Shippo hook later)."""
    code = "RN-" + secrets.token_hex(4).upper()
    label = {
        "label_id": code,
        "carrier": order.carrier or "USPS",
        "tracking_number": f"RZ{secrets.token_hex(8).upper()}",
        "status": "created",
        "note": "Prepaid return label created. Drop the package at any carrier location.",
        "order_id": order.id,
    }
    # Stash on a lightweight dispute/context isn't ideal; callers store on conversation.
    seller = session.get(Seller, order.seller_id) if order.seller_id else None
    if order.buyer_user_id:
        notify(
            session, order.buyer_user_id, "return_label",
            f"Return label ready — {order.title}",
            body=f"Label {code}. Tracking: {label['tracking_number']}",
            link="/account#orders",
        )
    notify_seller(
        session, seller, "return_started",
        f"Return started on order #{order.id}",
        body=f"Buyer return label {code} created.",
        link="/account#orders",
    )
    return label


def open_dispute(
    session: Session,
    order: Order,
    *,
    user_id: Optional[int],
    reason: str,
) -> dict:
    existing = session.exec(
        select(Dispute).where(Dispute.order_id == order.id, Dispute.status == "open")
    ).first()
    if existing:
        return {"dispute_id": existing.id, "status": "already_open"}
    dispute = Dispute(
        order_id=order.id,
        opened_by_user_id=user_id,
        reason=(reason or "Opened by AI Support")[:1000],
    )
    order.status = OrderStatus.disputed.value
    order.updated_at = utcnow()
    session.add(dispute)
    session.add(order)
    session.commit()
    session.refresh(dispute)
    notify_admins(
        session, "dispute_opened",
        f"Dispute on order #{order.id} — {order.title}",
        body=(reason or "")[:200], link="/admin",
    )
    return {"dispute_id": dispute.id, "status": "open"}


def flag_human_review(
    session: Session,
    conv: SupportConversation,
    *,
    reason: str,
) -> None:
    notify_admins(
        session, "support_escalation",
        f"Support case {conv.public_id} needs review",
        body=(reason or conv.intent or "escalated")[:200],
        link="/admin",
    )
    try:
        from .. import platform_events

        platform_events.emit(
            "support.escalated",
            {
                "conversation_id": conv.id,
                "public_id": conv.public_id,
                "intent": conv.intent,
                "reason": reason,
                "status": conv.status,
            },
        )
    except Exception:  # noqa: BLE001
        pass

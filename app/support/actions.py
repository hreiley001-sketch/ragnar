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
) -> dict:
    """Record refund + attempt Stripe when possible. Always updates order state."""
    total = order.price_cents + (order.shipping_cents or 0)
    amount_cents = max(0, min(amount_cents, total))
    kind = "partial" if amount_cents < total else kind

    stripe_id = None
    status = "recorded"
    stripe_result = payments_bridge.try_refund(order, amount_cents, reason=reason)
    if stripe_result.get("ok"):
        status = "stripe_refunded"
        stripe_id = stripe_result.get("refund_id")
    elif stripe_result.get("pending"):
        status = "recorded"  # ledger entry; money movement pending Stripe config

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

    # Cancel/close the order on full refund; leave delivered on partial.
    if kind == "full" or amount_cents >= total:
        order.status = OrderStatus.cancelled.value
    order.updated_at = utcnow()
    session.add(order)
    session.commit()
    session.refresh(row)
    session.refresh(order)

    if order.buyer_user_id:
        notify(
            session, order.buyer_user_id, "refund_issued",
            f"Refund issued — {order.title}",
            body=f"${amount_cents/100:.2f} refund recorded"
                 + (" via Stripe." if status == "stripe_refunded" else "."),
            link="/account#orders",
        )
    seller = session.get(Seller, order.seller_id) if order.seller_id else None
    notify_seller(
        session, seller, "refund_issued",
        f"Refund on order #{order.id}",
        body=f"${amount_cents/100:.2f} — {reason[:120] if reason else 'support refund'}",
        link="/account#orders",
    )
    return {
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

"""Stripe chargeback (charge.dispute) desk — Trust & Safety Wave 0.

Maps Stripe Dispute objects to local Chargeback rows, buyer-protection Dispute
records, TrustEvents, and fraud score updates.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlmodel import Session, select

from .models import (
    Chargeback,
    Dispute,
    Order,
    OrderStatus,
    Seller,
    utcnow,
)

logger = logging.getLogger("ragnar.chargebacks")

# Stripe dispute.status values we care about.
OPEN_STATUSES = {"needs_response", "warning_needs_response", "under_review", "warning_under_review"}
LOST_STATUSES = {"lost", "warning_closed"}
WON_STATUSES = {"won"}


def _parse_ts(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError, OSError):
        return None


def _pi_id(obj: dict) -> Optional[str]:
    pi = obj.get("payment_intent")
    if isinstance(pi, dict):
        return pi.get("id")
    if isinstance(pi, str) and pi:
        return pi
    return None


def _charge_id(obj: dict) -> Optional[str]:
    ch = obj.get("charge")
    if isinstance(ch, dict):
        return ch.get("id")
    if isinstance(ch, str) and ch:
        return ch
    return None


def find_order_for_dispute(session: Session, obj: dict) -> Optional[Order]:
    """Resolve Order from payment_intent, charge metadata, or session metadata."""
    pi = _pi_id(obj)
    if pi:
        order = session.exec(
            select(Order).where(Order.stripe_payment_intent_id == pi)
        ).first()
        if order:
            return order

    meta = obj.get("metadata") or {}
    listing_id = meta.get("listing_id")
    order_id = meta.get("order_id")
    if order_id:
        order = session.get(Order, int(order_id))
        if order:
            return order
    if listing_id:
        order = session.exec(
            select(Order)
            .where(Order.listing_id == int(listing_id))
            .order_by(Order.created_at.desc())
        ).first()
        if order:
            return order
    return None


def _ensure_buyer_dispute(
    session: Session,
    order: Order,
    *,
    reason: str,
) -> Dispute:
    existing = session.exec(
        select(Dispute).where(Dispute.order_id == order.id, Dispute.status == "open")
    ).first()
    if existing:
        return existing
    dispute = Dispute(
        order_id=order.id,  # type: ignore[arg-type]
        opened_by_user_id=order.buyer_user_id,
        reason=reason[:1000],
        status="open",
    )
    if order.status not in (OrderStatus.cancelled.value, OrderStatus.refunded.value):
        order.status = OrderStatus.disputed.value
        order.updated_at = utcnow()
        session.add(order)
    session.add(dispute)
    session.flush()
    return dispute


def apply_dispute_event(session: Session, obj: dict, event_type: str) -> dict:
    """Upsert Chargeback from a Stripe dispute object. Returns a summary dict."""
    dispute_id = obj.get("id")
    if not dispute_id:
        return {"ok": False, "reason": "missing dispute id"}

    status_value = (obj.get("status") or "needs_response").strip()
    reason = (obj.get("reason") or "").strip() or None
    amount = int(obj.get("amount") or 0)
    currency = (obj.get("currency") or "usd").lower()
    pi = _pi_id(obj)
    charge = _charge_id(obj)
    evidence_due = _parse_ts((obj.get("evidence_details") or {}).get("due_by"))

    order = find_order_for_dispute(session, obj)
    seller_id = order.seller_id if order else None
    if seller_id is None:
        # Destination charges may include connected account on transfer — best-effort skip.
        pass

    row = session.exec(
        select(Chargeback).where(Chargeback.stripe_dispute_id == dispute_id)
    ).first()
    created = False
    if not row:
        row = Chargeback(stripe_dispute_id=dispute_id)
        created = True

    prev_status = row.status if not created else None
    row.order_id = order.id if order else row.order_id
    row.seller_id = seller_id if seller_id is not None else row.seller_id
    row.stripe_charge_id = charge or row.stripe_charge_id
    row.stripe_payment_intent_id = pi or row.stripe_payment_intent_id
    row.status = status_value
    row.reason = reason or row.reason
    row.amount_cents = amount or row.amount_cents
    row.currency = currency
    row.evidence_due_by = evidence_due or row.evidence_due_by
    row.updated_at = utcnow()
    if status_value in LOST_STATUSES | WON_STATUSES:
        row.closed_at = row.closed_at or utcnow()

    local_dispute = None
    if order and status_value in OPEN_STATUSES:
        local_dispute = _ensure_buyer_dispute(
            session,
            order,
            reason=f"Stripe chargeback ({reason or 'unknown'}): {dispute_id}",
        )
        row.dispute_id = local_dispute.id

    session.add(row)
    session.flush()

    # Trust impact
    seller = session.get(Seller, row.seller_id) if row.seller_id else None
    score_info = None
    if seller:
        from . import trust as trust_svc

        if created or (prev_status != status_value and status_value in OPEN_STATUSES):
            trust_svc.record_event(
                session,
                seller,
                "chargeback_opened" if created else "chargeback_updated",
                detail=f"{event_type} {dispute_id} status={status_value} reason={reason}",
                score_before=seller.fraud_score,
                score_after=seller.fraud_score,
            )
            # Hard bump then recompute so chargebacks always move the needle.
            before = int(seller.fraud_score or 0)
            seller.fraud_score = min(100, before + 20)
            session.add(seller)
            after = trust_svc.recompute_fraud_score(
                session, seller, detail=f"after chargeback {dispute_id}"
            )
            # Keep at least the bump if recompute is lower (heuristic may lag).
            if after < min(100, before + 20):
                seller.fraud_score = min(100, before + 20)
                session.add(seller)
                after = seller.fraud_score
            score_info = {"before": before, "after": after}

        if status_value in LOST_STATUSES:
            trust_svc.record_event(
                session,
                seller,
                "chargeback_lost",
                detail=f"{dispute_id} amount_cents={amount}",
                score_before=seller.fraud_score,
                score_after=seller.fraud_score,
            )
            trust_svc.recompute_fraud_score(session, seller, detail=f"chargeback lost {dispute_id}")
            if local_dispute is None and row.dispute_id:
                local_dispute = session.get(Dispute, row.dispute_id)
            if local_dispute and local_dispute.status == "open":
                local_dispute.status = "resolved_refund"
                local_dispute.resolution = f"Stripe chargeback lost ({dispute_id})"
                local_dispute.resolved_at = utcnow()
                session.add(local_dispute)
                if order and order.status == OrderStatus.disputed.value:
                    order.status = OrderStatus.refunded.value
                    order.updated_at = utcnow()
                    session.add(order)

        if status_value in WON_STATUSES:
            trust_svc.record_event(
                session,
                seller,
                "chargeback_won",
                detail=f"{dispute_id}",
                score_before=seller.fraud_score,
                score_after=seller.fraud_score,
            )
            if local_dispute is None and row.dispute_id:
                local_dispute = session.get(Dispute, row.dispute_id)
            if local_dispute and local_dispute.status == "open":
                local_dispute.status = "resolved_denied"
                local_dispute.resolution = f"Stripe chargeback won by seller ({dispute_id})"
                local_dispute.resolved_at = utcnow()
                session.add(local_dispute)
                if order and order.status == OrderStatus.disputed.value:
                    order.status = OrderStatus.delivered.value
                    order.updated_at = utcnow()
                    session.add(order)
            trust_svc.recompute_fraud_score(session, seller, detail=f"chargeback won {dispute_id}")

    session.commit()
    session.refresh(row)

    # Notifications / automation (best-effort)
    try:
        from .emailer import ops_alert
        from .notify import notify_admins, notify_seller

        if created:
            ops_alert(
                f"Chargeback opened: {dispute_id} "
                f"(${amount / 100:.2f} {currency}) order={order.id if order else '—'}"
            )
            notify_admins(
                session,
                "chargeback_opened",
                f"Chargeback {dispute_id}",
                body=f"{reason or 'unknown'} · ${amount / 100:.2f}",
                link="/admin",
            )
            if seller:
                notify_seller(
                    session,
                    seller,
                    "chargeback_opened",
                    f"Chargeback on order #{order.id}" if order else "Chargeback received",
                    body="Evidence may be required — check Stripe / Command Hub.",
                    link="/account#store",
                )
        from .automation import emit_bg
        emit_bg(
            "chargeback.opened" if created else "chargeback.updated",
            {
                "chargeback_id": row.id,
                "stripe_dispute_id": dispute_id,
                "status": status_value,
                "order_id": order.id if order else None,
                "seller_id": row.seller_id,
                "amount_cents": amount,
                "reason": reason,
                "event_type": event_type,
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception("chargeback notify/emit failed")

    return {
        "ok": True,
        "created": created,
        "chargeback_id": row.id,
        "stripe_dispute_id": dispute_id,
        "status": status_value,
        "order_id": order.id if order else None,
        "seller_id": row.seller_id,
        "score": score_info,
    }


def list_chargebacks(session: Session, *, limit: int = 100) -> list[dict]:
    rows = session.exec(
        select(Chargeback).order_by(Chargeback.created_at.desc()).limit(limit)
    ).all()
    return [
        {
            "id": r.id,
            "stripe_dispute_id": r.stripe_dispute_id,
            "order_id": r.order_id,
            "seller_id": r.seller_id,
            "dispute_id": r.dispute_id,
            "status": r.status,
            "reason": r.reason,
            "amount_cents": r.amount_cents,
            "currency": r.currency,
            "evidence_due_by": r.evidence_due_by.isoformat() if r.evidence_due_by else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "closed_at": r.closed_at.isoformat() if r.closed_at else None,
        }
        for r in rows
    ]

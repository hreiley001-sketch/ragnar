"""Orders — buyer/seller order management, shipping + tracking, feedback,
and buyer-protection disputes (plus the admin views that resolve them).

Money crosses the API boundary in dollars; the DB stores integer cents.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..auth import can_act_for_seller, get_current_user, is_staff, require_user
from ..database import get_session
from ..models import Dispute, Feedback, Order, OrderStatus, Seller, User, utcnow
from ..notify import notify, notify_admins, notify_seller
from ..shipping import tracking_url
from .admin import require_admin

router = APIRouter(prefix="/api/orders", tags=["orders"])
admin_router = APIRouter(prefix="/api/admin", tags=["admin-orders"])


# --------------------------- payloads --------------------------- #

class ShipPayload(BaseModel):
    tracking_number: str = Field(min_length=1, max_length=80)
    carrier: Optional[str] = Field(default=None, max_length=40)


class FeedbackPayload(BaseModel):
    stars: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=1000)


class DisputePayload(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


class ResolvePayload(BaseModel):
    status: str
    resolution: Optional[str] = Field(default=None, max_length=1000)


# --------------------------- helpers --------------------------- #

def _order_or_404(session: Session, order_id: int) -> Order:
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


def _seller_or_404(session: Session, handle: str) -> Seller:
    seller = session.exec(
        select(Seller).where(Seller.handle == handle.strip().lower())
    ).first()
    if not seller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    return seller


def _order_dict(session: Session, o: Order, *, include_buyer: bool = False) -> dict:
    seller = session.get(Seller, o.seller_id) if o.seller_id else None
    feedback_left = session.exec(
        select(Feedback.id).where(Feedback.order_id == o.id).limit(1)
    ).first() is not None
    disputed = session.exec(
        select(Dispute.id).where(Dispute.order_id == o.id, Dispute.status == "open").limit(1)
    ).first() is not None
    d = {
        "id": o.id,
        "listing_id": o.listing_id,
        "title": o.title,
        "price": round(o.price_cents / 100, 2),
        "shipping": round(o.shipping_cents / 100, 2),
        "total": round((o.price_cents + o.shipping_cents) / 100, 2),
        "status": o.status,
        "tracking_number": o.tracking_number,
        "carrier": o.carrier,
        "tracking_url": tracking_url(o.carrier, o.tracking_number),
        "seller_handle": seller.handle if seller else None,
        "created_at": o.created_at.isoformat(),
        "feedback_left": feedback_left,
        "disputed": disputed,
    }
    if include_buyer:
        d["buyer_name"] = o.buyer_name
        d["buyer_email"] = o.buyer_email
    return d


def _dispute_dict(session: Session, d: Dispute) -> dict:
    order = session.get(Order, d.order_id)
    return {
        "id": d.id,
        "order_id": d.order_id,
        "order_title": order.title if order else None,
        "reason": d.reason,
        "status": d.status,
        "resolution": d.resolution,
        "created_at": d.created_at.isoformat(),
        "resolved_at": d.resolved_at.isoformat() if d.resolved_at else None,
    }


def _can_manage_order(session: Session, order: Order, user: Optional[User],
                      x_store_token: str) -> bool:
    """Staff, or someone who can act for the order's seller (owner/store token)."""
    if is_staff(user):
        return True
    seller = session.get(Seller, order.seller_id) if order.seller_id else None
    return can_act_for_seller(user, seller, x_store_token)


# --------------------------- buyer / seller endpoints --------------------------- #

@router.get("/mine")
def my_orders(
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    orders = session.exec(
        select(Order).where(Order.buyer_user_id == user.id).order_by(Order.created_at.desc())
    ).all()
    return {"items": [_order_dict(session, o) for o in orders]}


@router.get("/store/{handle}/rating")
def store_rating(handle: str, session: Session = Depends(get_session)) -> dict:
    """Public seller rating aggregate."""
    seller = _seller_or_404(session, handle)
    rows = session.exec(select(Feedback.stars).where(Feedback.seller_id == seller.id)).all()
    count = len(rows)
    avg = round(sum(rows) / count, 2) if count else None
    return {"avg_stars": avg, "count": count}


@router.get("/store/{handle}")
def store_orders(
    handle: str,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
    x_store_token: str = Header(default=""),
) -> dict:
    seller = _seller_or_404(session, handle)
    if not (is_staff(user) or can_act_for_seller(user, seller, x_store_token)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in as this store's owner or provide X-Store-Token.",
        )
    orders = session.exec(
        select(Order).where(Order.seller_id == seller.id).order_by(Order.created_at.desc())
    ).all()
    return {"items": [_order_dict(session, o, include_buyer=True) for o in orders]}


@router.post("/{order_id}/ship")
def ship_order(
    order_id: int,
    payload: ShipPayload,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
    x_store_token: str = Header(default=""),
) -> dict:
    order = _order_or_404(session, order_id)
    if not _can_manage_order(session, order, user, x_store_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Only the seller (or staff) can mark an order shipped.",
        )
    if order.status not in (OrderStatus.paid.value, OrderStatus.pending.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order is '{order.status}' — only paid/pending orders can be shipped.",
        )
    order.tracking_number = payload.tracking_number.strip()
    order.carrier = payload.carrier.strip() if payload.carrier else None
    order.status = OrderStatus.shipped.value
    order.updated_at = utcnow()
    session.add(order)
    session.commit()
    session.refresh(order)
    if order.buyer_user_id:
        notify(
            session, order.buyer_user_id, "order_shipped",
            f"Your order shipped — {order.title}",
            body=f"Tracking number: {order.tracking_number}"
                 + (f" ({order.carrier})" if order.carrier else ""),
            link="/account#orders",
        )
    return _order_dict(session, order)


@router.post("/{order_id}/delivered")
def mark_delivered(
    order_id: int,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
    x_store_token: str = Header(default=""),
) -> dict:
    order = _order_or_404(session, order_id)
    is_buyer = bool(user and order.buyer_user_id and order.buyer_user_id == user.id)
    if not (is_buyer or _can_manage_order(session, order, user, x_store_token)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Only the buyer or seller (or staff) can mark an order delivered.",
        )
    if order.status != OrderStatus.shipped.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order is '{order.status}' — only shipped orders can be marked delivered.",
        )
    order.status = OrderStatus.delivered.value
    order.updated_at = utcnow()
    session.add(order)
    session.commit()
    session.refresh(order)
    # Tell the other party.
    if is_buyer:
        seller = session.get(Seller, order.seller_id) if order.seller_id else None
        notify_seller(
            session, seller, "order_delivered",
            f"Order delivered — {order.title}",
            body="The buyer confirmed delivery.",
            link="/account#orders",
        )
    elif order.buyer_user_id:
        notify(
            session, order.buyer_user_id, "order_delivered",
            f"Order delivered — {order.title}",
            body="The seller marked your order as delivered.",
            link="/account#orders",
        )
    return _order_dict(session, order)


@router.post("/{order_id}/feedback")
def leave_feedback(
    order_id: int,
    payload: FeedbackPayload,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    order = _order_or_404(session, order_id)
    if order.buyer_user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the buyer can leave feedback on this order.",
        )
    if order.status not in (
        OrderStatus.paid.value, OrderStatus.shipped.value, OrderStatus.delivered.value
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order is '{order.status}' — feedback requires a paid/shipped/delivered order.",
        )
    existing = session.exec(
        select(Feedback.id).where(Feedback.order_id == order.id).limit(1)
    ).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Feedback already left for this order.",
        )
    if order.seller_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This order has no seller to rate.",
        )
    fb = Feedback(
        order_id=order.id,
        seller_id=order.seller_id,
        rater_user_id=user.id,
        stars=payload.stars,
        comment=(payload.comment or "").strip() or None,
    )
    session.add(fb)
    session.commit()
    seller = session.get(Seller, order.seller_id)
    notify_seller(
        session, seller, "feedback_received",
        f"New feedback — {payload.stars}/5 stars",
        body=f"{order.title}" + (f': "{fb.comment[:150]}"' if fb.comment else ""),
        link="/account#orders",
    )
    return {"status": "ok", "stars": payload.stars}


@router.post("/{order_id}/dispute")
def open_dispute(
    order_id: int,
    payload: DisputePayload,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    order = _order_or_404(session, order_id)
    if order.buyer_user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the buyer can open a dispute on this order.",
        )
    if order.status in (OrderStatus.disputed.value, OrderStatus.cancelled.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order is already '{order.status}'.",
        )
    reason = payload.reason.strip()
    dispute = Dispute(order_id=order.id, opened_by_user_id=user.id, reason=reason)
    order.status = OrderStatus.disputed.value
    order.updated_at = utcnow()
    session.add(dispute)
    session.add(order)
    session.commit()
    session.refresh(dispute)
    notify_admins(
        session, "dispute_opened",
        f"Dispute on order #{order.id} — {order.title}",
        body=reason[:200], link="/admin",
    )
    seller = session.get(Seller, order.seller_id) if order.seller_id else None
    notify_seller(
        session, seller, "dispute_opened",
        f"Dispute on order #{order.id} — {order.title}",
        body=reason[:200], link="/account#orders",
    )
    return {"status": "disputed", "dispute_id": dispute.id}


# --------------------------- admin --------------------------- #

@admin_router.get("/orders")
def admin_orders(
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
) -> dict:
    orders = session.exec(
        select(Order).order_by(Order.created_at.desc()).limit(200)
    ).all()
    return {"items": [_order_dict(session, o, include_buyer=True) for o in orders]}


@admin_router.get("/disputes")
def admin_disputes(
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
) -> dict:
    disputes = session.exec(select(Dispute).order_by(Dispute.created_at.desc())).all()
    return {"items": [_dispute_dict(session, d) for d in disputes]}


@admin_router.post("/disputes/{dispute_id}/resolve")
def resolve_dispute(
    dispute_id: int,
    payload: ResolvePayload,
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
) -> dict:
    dispute = session.get(Dispute, dispute_id)
    if not dispute:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispute not found")
    if dispute.status != "open":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dispute is already '{dispute.status}'.",
        )
    if payload.status not in ("resolved_refund", "resolved_denied"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="status must be 'resolved_refund' or 'resolved_denied'.",
        )
    dispute.status = payload.status
    dispute.resolution = (payload.resolution or "").strip() or None
    dispute.resolved_at = utcnow()
    session.add(dispute)

    order = session.get(Order, dispute.order_id)
    if order:
        order.status = (
            OrderStatus.cancelled.value if payload.status == "resolved_refund"
            else OrderStatus.delivered.value
        )
        order.updated_at = utcnow()
        session.add(order)
    session.commit()
    session.refresh(dispute)

    outcome = "refund issued" if payload.status == "resolved_refund" else "dispute denied"
    if order:
        if order.buyer_user_id:
            notify(
                session, order.buyer_user_id, "dispute_resolved",
                f"Dispute resolved — {outcome}",
                body=dispute.resolution or f"Order: {order.title}",
                link="/account#orders",
            )
        seller = session.get(Seller, order.seller_id) if order.seller_id else None
        notify_seller(
            session, seller, "dispute_resolved",
            f"Dispute resolved — {outcome}",
            body=dispute.resolution or f"Order: {order.title}",
            link="/account#orders",
        )
    return _dispute_dict(session, dispute)

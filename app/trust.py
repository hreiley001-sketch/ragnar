"""Trust & Safety spine — verification, fraud scoring, suspension enforcement.

See vault/Ragnarips/TrustSafety/README.md for the operating blueprint.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from fastapi import HTTPException, status
from sqlmodel import Session, select

from .models import (
    Chargeback,
    Dispute,
    Feedback,
    Order,
    Seller,
    SellerTrustStatus,
    SellerVerificationStatus,
    TrustEvent,
    utcnow,
)

# Fraud score bands (ops defaults — status changes stay human-gated in v1).
SCORE_WATCH = 30
SCORE_RESTRICT_CANDIDATE = 60
SCORE_SUSPEND_CANDIDATE = 80


class TrustError(Exception):
    """Raised when a seller is not allowed to perform a marketplace action."""


def _status(seller: Seller) -> str:
    return (seller.trust_status or SellerTrustStatus.active.value).strip().lower()


def can_list(seller: Seller) -> bool:
    return _status(seller) == SellerTrustStatus.active.value


def can_sell(seller: Seller) -> bool:
    """Checkout / fulfill — blocked for suspended and banned."""
    return _status(seller) in {
        SellerTrustStatus.active.value,
        SellerTrustStatus.restricted.value,
    }


def can_go_live(seller: Seller) -> bool:
    return _status(seller) == SellerTrustStatus.active.value


def assert_can_list(seller: Seller) -> None:
    if can_list(seller):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Seller '{seller.handle}' cannot create listings "
        f"(trust status: {_status(seller)}).",
    )


def assert_can_sell(seller: Seller) -> None:
    if can_sell(seller):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Seller '{seller.handle}' cannot accept checkout "
        f"(trust status: {_status(seller)}).",
    )


def assert_can_go_live(seller: Seller) -> None:
    if can_go_live(seller):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Seller '{seller.handle}' cannot go live "
        f"(trust status: {_status(seller)}).",
    )


def record_event(
    session: Session,
    seller: Seller,
    event_type: str,
    *,
    actor_user_id: Optional[int] = None,
    detail: Optional[str] = None,
    score_before: Optional[int] = None,
    score_after: Optional[int] = None,
) -> TrustEvent:
    ev = TrustEvent(
        seller_id=seller.id,  # type: ignore[arg-type]
        actor_user_id=actor_user_id,
        event_type=event_type,
        detail=(detail or None),
        score_before=score_before,
        score_after=score_after,
    )
    session.add(ev)
    return ev


def compute_fraud_score(session: Session, seller: Seller) -> int:
    """Heuristic 0–100 risk score. Higher = riskier. See TrustSafety blueprint."""
    score = 0

    order_ids = [
        o.id
        for o in session.exec(select(Order).where(Order.seller_id == seller.id)).all()
        if o.id is not None
    ]
    if order_ids:
        disputes = session.exec(
            select(Dispute).where(Dispute.order_id.in_(order_ids))  # type: ignore[attr-defined]
        ).all()
        open_n = sum(1 for d in disputes if d.status == "open")
        refund_n = sum(1 for d in disputes if d.status == "resolved_refund")
        denied_n = sum(1 for d in disputes if d.status == "resolved_denied")
        score += min(45, open_n * 15)
        score += min(30, refund_n * 10)
        score = max(0, score - min(25, denied_n * 5))

    since = utcnow() - timedelta(days=90)
    low_fb = session.exec(
        select(Feedback).where(
            Feedback.seller_id == seller.id,
            Feedback.stars <= 2,
            Feedback.created_at >= since,
        )
    ).all()
    score += min(24, len(low_fb) * 8)

    open_cbs = session.exec(
        select(Chargeback).where(
            Chargeback.seller_id == seller.id,
            Chargeback.status.in_(  # type: ignore[attr-defined]
                [
                    "needs_response",
                    "warning_needs_response",
                    "under_review",
                    "warning_under_review",
                ]
            ),
        )
    ).all()
    score += min(40, len(open_cbs) * 20)
    lost_cbs = session.exec(
        select(Chargeback).where(
            Chargeback.seller_id == seller.id,
            Chargeback.status.in_(["lost", "warning_closed"]),  # type: ignore[attr-defined]
        )
    ).all()
    score += min(30, len(lost_cbs) * 15)

    if seller.verification_status == SellerVerificationStatus.verified.value:
        score = max(0, score - 10)
    if seller.stripe_charges_enabled:
        score = max(0, score - 5)

    return max(0, min(100, score))


def risk_band(score: int) -> str:
    if score >= SCORE_SUSPEND_CANDIDATE:
        return "critical"
    if score >= SCORE_RESTRICT_CANDIDATE:
        return "high"
    if score >= SCORE_WATCH:
        return "watch"
    return "green"


def recompute_fraud_score(
    session: Session,
    seller: Seller,
    *,
    actor_user_id: Optional[int] = None,
    detail: Optional[str] = None,
) -> int:
    before = int(seller.fraud_score or 0)
    after = compute_fraud_score(session, seller)
    seller.fraud_score = after
    session.add(seller)
    record_event(
        session,
        seller,
        "fraud_score_recomputed",
        actor_user_id=actor_user_id,
        detail=detail or f"band={risk_band(after)}",
        score_before=before,
        score_after=after,
    )
    return after


def set_verification(
    session: Session,
    seller: Seller,
    status_value: str,
    *,
    actor_user_id: Optional[int] = None,
    id_verification_ref: Optional[str] = None,
    detail: Optional[str] = None,
) -> Seller:
    allowed = {s.value for s in SellerVerificationStatus}
    if status_value not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"verification_status must be one of {sorted(allowed)}",
        )
    before = seller.verification_status
    seller.verification_status = status_value
    if status_value == SellerVerificationStatus.verified.value:
        seller.verified_at = utcnow()
    elif status_value in {
        SellerVerificationStatus.unverified.value,
        SellerVerificationStatus.rejected.value,
    }:
        seller.verified_at = None
    if id_verification_ref is not None:
        seller.id_verification_ref = id_verification_ref.strip() or None
    session.add(seller)
    record_event(
        session,
        seller,
        "verification_updated",
        actor_user_id=actor_user_id,
        detail=detail or f"{before} → {status_value}",
        score_before=seller.fraud_score,
        score_after=seller.fraud_score,
    )
    recompute_fraud_score(
        session, seller, actor_user_id=actor_user_id, detail="after verification change"
    )
    return seller


def set_trust_status(
    session: Session,
    seller: Seller,
    status_value: str,
    *,
    actor_user_id: Optional[int] = None,
    reason: Optional[str] = None,
) -> Seller:
    allowed = {s.value for s in SellerTrustStatus}
    if status_value not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"trust_status must be one of {sorted(allowed)}",
        )
    before = _status(seller)
    seller.trust_status = status_value
    if status_value in {
        SellerTrustStatus.suspended.value,
        SellerTrustStatus.banned.value,
        SellerTrustStatus.restricted.value,
    }:
        seller.suspension_reason = (reason or seller.suspension_reason or "").strip() or None
        seller.suspended_at = utcnow()
    elif status_value == SellerTrustStatus.active.value:
        seller.suspension_reason = None
        seller.suspended_at = None
    session.add(seller)
    record_event(
        session,
        seller,
        "trust_status_updated",
        actor_user_id=actor_user_id,
        detail=(reason or f"{before} → {status_value}")[:2000],
        score_before=seller.fraud_score,
        score_after=seller.fraud_score,
    )
    return seller


def public_badge(session: Session, seller: Seller) -> dict:
    """Buyer-facing trust snapshot — never expose raw fraud_score."""
    from sqlmodel import func

    fb_stats = session.exec(
        select(func.count(Feedback.id), func.avg(Feedback.stars)).where(
            Feedback.seller_id == seller.id
        )
    ).one()
    count = int(fb_stats[0] or 0)
    avg = float(fb_stats[1]) if fb_stats[1] is not None else None
    return {
        "handle": seller.handle,
        "display_name": seller.display_name,
        "verified": seller.verification_status == SellerVerificationStatus.verified.value,
        "verification_status": seller.verification_status,
        "trust_status": _status(seller),
        "is_founding": bool(seller.is_founding),
        "stripe_ready": bool(seller.stripe_charges_enabled),
        "rating": {
            "count": count,
            "average": round(avg, 2) if avg is not None else None,
        },
        "buyer_protection": True,
    }


def admin_snapshot(session: Session, seller: Seller) -> dict:
    badge = public_badge(session, seller)
    badge.update({
        "fraud_score": int(seller.fraud_score or 0),
        "risk_band": risk_band(int(seller.fraud_score or 0)),
        "suspension_reason": seller.suspension_reason,
        "suspended_at": seller.suspended_at.isoformat() if seller.suspended_at else None,
        "verified_at": seller.verified_at.isoformat() if seller.verified_at else None,
        "id_verification_ref": seller.id_verification_ref,
        "trust_notes": seller.trust_notes,
        "email": seller.email,
        "is_founding": seller.is_founding,
        "founding_number": seller.founding_number,
        "stripe_connected": bool(seller.stripe_account_id),
        "stripe_charges_enabled": seller.stripe_charges_enabled,
    })
    return badge

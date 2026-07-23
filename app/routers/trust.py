"""Public trust badge + thin admin trust helpers mounted from main/admin."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from ..auth import get_current_user
from ..database import get_session
from ..models import Seller, TrustEvent
from .. import trust as trust_svc
from .admin import require_admin

router = APIRouter(prefix="/api/trust", tags=["trust"])
admin_router = APIRouter(prefix="/api/admin/trust", tags=["admin-trust"])


def _seller_by_handle(session: Session, handle: str) -> Seller:
    seller = session.exec(
        select(Seller).where(Seller.handle == handle.strip().lower())
    ).first()
    if not seller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seller not found")
    return seller


@router.get("/sellers/{handle}")
def seller_trust_badge(handle: str, session: Session = Depends(get_session)) -> dict:
    """Public buyer-facing trust badge (no fraud score)."""
    seller = _seller_by_handle(session, handle)
    return trust_svc.public_badge(session, seller)


@admin_router.get("/sellers/{handle}")
def admin_seller_trust(
    handle: str,
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
) -> dict:
    seller = _seller_by_handle(session, handle)
    snap = trust_svc.admin_snapshot(session, seller)
    events = session.exec(
        select(TrustEvent)
        .where(TrustEvent.seller_id == seller.id)
        .order_by(TrustEvent.created_at.desc())
        .limit(50)
    ).all()
    snap["events"] = [
        {
            "id": e.id,
            "event_type": e.event_type,
            "detail": e.detail,
            "score_before": e.score_before,
            "score_after": e.score_after,
            "actor_user_id": e.actor_user_id,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
    ]
    return snap


@admin_router.post("/sellers/{handle}/verify")
def admin_verify_seller(
    handle: str,
    payload: dict,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
    _: None = Depends(require_admin),
) -> dict:
    seller = _seller_by_handle(session, handle)
    status_value = (payload.get("verification_status") or "verified").strip().lower()
    trust_svc.set_verification(
        session,
        seller,
        status_value,
        actor_user_id=user.id if user else None,
        id_verification_ref=payload.get("id_verification_ref"),
        detail=payload.get("detail"),
    )
    session.commit()
    session.refresh(seller)
    return trust_svc.admin_snapshot(session, seller)


@admin_router.post("/sellers/{handle}/status")
def admin_set_trust_status(
    handle: str,
    payload: dict,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
    _: None = Depends(require_admin),
) -> dict:
    seller = _seller_by_handle(session, handle)
    status_value = (payload.get("trust_status") or "").strip().lower()
    if not status_value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="trust_status required")
    trust_svc.set_trust_status(
        session,
        seller,
        status_value,
        actor_user_id=user.id if user else None,
        reason=payload.get("reason"),
    )
    if payload.get("notes"):
        seller.trust_notes = str(payload["notes"])[:2000]
        session.add(seller)
    session.commit()
    session.refresh(seller)
    return trust_svc.admin_snapshot(session, seller)


@admin_router.post("/sellers/{handle}/rescore")
def admin_rescore_seller(
    handle: str,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
    _: None = Depends(require_admin),
) -> dict:
    seller = _seller_by_handle(session, handle)
    trust_svc.recompute_fraud_score(
        session,
        seller,
        actor_user_id=user.id if user else None,
        detail="manual admin rescore",
    )
    session.commit()
    session.refresh(seller)
    return trust_svc.admin_snapshot(session, seller)


@admin_router.get("/chargebacks")
def admin_chargebacks(
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
) -> dict:
    from .. import chargebacks
    items = chargebacks.list_chargebacks(session)
    return {"items": items, "count": len(items)}

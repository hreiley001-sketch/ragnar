"""Dispatch API — AI shipping agent chat + seller tools + admin queue."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..auth import get_current_user, is_staff, require_user
from ..database import get_session
from ..models import (
    Seller,
    ShippingCaseStatus,
    ShippingConversation,
    ShippingMessage,
    User,
    utcnow,
)
from ..notify import notify
from ..routers.admin import require_admin
from ..shipping_agent import brain, knowledge
from ..shipping_agent import actions, governance
from .. import shipping as ship

router = APIRouter(prefix="/api/shipping", tags=["shipping"])
admin_router = APIRouter(prefix="/api/admin/shipping", tags=["admin-shipping"])


class StartPayload(BaseModel):
    channel: str = Field(default="web", max_length=20)
    seller_handle: Optional[str] = Field(default=None, max_length=40)


class MessagePayload(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: Optional[str] = Field(default=None, max_length=32)


class AddressPayload(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    street1: str = Field(min_length=1, max_length=120)
    city: str = Field(min_length=1, max_length=80)
    state: str = Field(min_length=1, max_length=40)
    zip: str = Field(min_length=3, max_length=20)
    country: str = Field(default="US", max_length=2)
    phone: Optional[str] = Field(default=None, max_length=40)
    prefer: str = Field(default="balanced", max_length=20)


class ResolvePayload(BaseModel):
    resolution: str = Field(min_length=1, max_length=1000)
    status: str = Field(default="resolved")


def _seller_for_user(session: Session, user: Optional[User]) -> Optional[Seller]:
    if not user or not user.email:
        return None
    return session.exec(select(Seller).where(Seller.email == user.email)).first()


def _conv_dict(session: Session, conv: ShippingConversation, *, with_messages: bool = False) -> dict:
    d = {
        "id": conv.public_id,
        "status": conv.status,
        "intent": conv.intent,
        "confidence": conv.confidence,
        "tone": conv.tone,
        "queue": conv.queue,
        "order_id": conv.order_id,
        "seller_id": conv.seller_id,
        "workflow": conv.workflow,
        "workflow_step": conv.workflow_step,
        "entities": conv.entities or {},
        "context": conv.context or {},
        "channel": conv.channel,
        "user_id": conv.user_id,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
        "resolved_at": conv.resolved_at.isoformat() if conv.resolved_at else None,
    }
    if with_messages:
        d["messages"] = brain.messages_for(session, conv)
    return d


@router.get("/status")
def shipping_status() -> dict:
    return {
        "shippo": ship.is_configured(),
        "agent": "dispatch",
        "capabilities": [
            "quote_rates", "recommend_packaging", "create_label", "ship_order",
            "track_shipment", "list_to_ship", "validate_address", "handle_exception",
        ],
    }


@router.post("/conversations")
def start_dispatch(
    payload: StartPayload | None = None,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
) -> dict:
    seller_id = None
    if payload and payload.seller_handle:
        seller = session.exec(
            select(Seller).where(Seller.handle == payload.seller_handle.strip().lower())
        ).first()
        if seller:
            seller_id = seller.id
    channel = (payload.channel if payload else "web") or "web"
    conv = brain.start_conversation(session, user=user, channel=channel, seller_id=seller_id)
    return {
        **_conv_dict(session, conv, with_messages=True),
        "reply": brain.messages_for(session, conv)[-1]["body"] if brain.messages_for(session, conv) else "",
        "chips": [
            "Orders to ship", "Create a label", "Quote shipping rates",
            "How should I pack a slab?",
        ],
    }


@router.get("/conversations/{public_id}")
def get_dispatch_conversation(
    public_id: str,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
) -> dict:
    conv = brain.get_conversation(session, public_id, user=user, staff=is_staff(user))
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return _conv_dict(session, conv, with_messages=True)


@router.post("/chat")
def dispatch_chat(
    payload: MessagePayload,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
) -> dict:
    text = payload.message.strip()
    if payload.conversation_id:
        conv = brain.get_conversation(
            session, payload.conversation_id, user=user, staff=is_staff(user),
        )
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conv = brain.start_conversation(session, user=user, channel="web")

    if text.lower().strip() in {"talk to a human", "human", "agent", "escalate"}:
        governance.escalate_conversation(
            session, conv, queue="shipping", reason="Seller requested human help",
        )
        actions.flag_human_review(session, conv, reason="Seller requested human")
        reply = (
            "I've moved this to the shipping review queue. A teammate will pick it up. "
            f"Case id: {conv.public_id}."
        )
        brain.add_message(session, conv, "user", text)
        brain.add_message(session, conv, "assistant", reply, meta={"escalated": True})
        return {**_conv_dict(session, conv), "reply": reply, "decision": "escalate", "chips": []}

    result = brain.handle_message(session, conv, text, user=user)
    return {
        **_conv_dict(session, conv),
        **result,
        "chips": result.get("chips") or [
            "Orders to ship", "Create a label", "Quote shipping rates",
        ],
    }


@router.get("/to-ship")
def to_ship_queue(
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    seller = _seller_for_user(session, user)
    items = actions.list_to_ship(
        session,
        seller_id=None if is_staff(user) else (seller.id if seller else -1),
        limit=50,
    )
    if not is_staff(user) and not seller:
        return {"items": [], "note": "Sign in with a seller account to see your queue."}
    return {"items": [actions.order_summary(session, o) for o in items]}


@router.get("/profile")
def get_shipping_profile(
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    seller = _seller_for_user(session, user)
    if not seller:
        raise HTTPException(status_code=404, detail="No seller account linked to this user")
    row = actions.get_profile(session, seller.id)
    if not row:
        return {"seller_id": seller.id, "handle": seller.handle, "configured": False}
    return {
        "seller_id": seller.id,
        "handle": seller.handle,
        "configured": bool(row.street1),
        "name": row.name,
        "street1": row.street1,
        "city": row.city,
        "state": row.state,
        "zip": row.zip,
        "country": row.country,
        "phone": row.phone,
        "prefer": row.prefer,
    }


@router.put("/profile")
def put_shipping_profile(
    payload: AddressPayload,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    seller = _seller_for_user(session, user)
    if not seller:
        raise HTTPException(status_code=404, detail="No seller account linked to this user")
    prefer = payload.prefer if payload.prefer in ("cheapest", "fastest", "balanced") else "balanced"
    row = actions.upsert_ship_from(
        session,
        seller_id=seller.id,
        address=payload.model_dump(),
        prefer=prefer,
    )
    return {
        "ok": True,
        "configured": True,
        "street1": row.street1,
        "city": row.city,
        "state": row.state,
        "zip": row.zip,
        "prefer": row.prefer,
    }


@router.post("/validate-address")
def validate_address_endpoint(payload: AddressPayload) -> dict:
    return ship.validate_address(payload.model_dump())


@router.get("/packaging")
def packaging_advice(
    graded: bool = False,
    value: float = Query(default=0, ge=0),
    quantity: int = Query(default=1, ge=1, le=50),
) -> dict:
    return ship.recommend_packaging(
        is_graded=graded,
        quantity=quantity,
        value_cents=int(round(value * 100)),
    )


@router.get("/knowledge")
def shipping_knowledge(
    q: str = Query(default="", max_length=200),
    session: Session = Depends(get_session),
) -> dict:
    return {"items": knowledge.search(session, q, limit=8)}


@router.get("/mine")
def my_dispatch_cases(
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    rows = session.exec(
        select(ShippingConversation)
        .where(ShippingConversation.user_id == user.id)
        .order_by(ShippingConversation.updated_at.desc())
        .limit(50)
    ).all()
    return {"items": [_conv_dict(session, c) for c in rows]}


# --------------------------- admin --------------------------- #

@admin_router.get("/queue")
def admin_shipping_queue(
    queue: Optional[str] = None,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
) -> dict:
    rows = governance.list_queue(session, queue=queue, status=status_filter)
    return {"items": [_conv_dict(session, c, with_messages=True) for c in rows]}


@admin_router.get("/conversations/{public_id}")
def admin_get_shipping_conversation(
    public_id: str,
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
) -> dict:
    conv = brain.get_conversation(session, public_id, staff=True)
    if not conv:
        raise HTTPException(status_code=404, detail="Not found")
    audits = governance.list_audit(session, conversation_id=conv.id)
    return {
        **_conv_dict(session, conv, with_messages=True),
        "audit": [
            {
                "id": a.id,
                "actor": a.actor,
                "intent": a.intent,
                "decision": a.decision,
                "actions": a.actions,
                "policy_refs": a.policy_refs,
                "confidence": a.confidence,
                "risk": a.risk,
                "reason": a.reason,
                "detail": a.detail,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in audits
        ],
    }


@admin_router.post("/conversations/{public_id}/resolve")
def admin_resolve_shipping(
    public_id: str,
    payload: ResolvePayload,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
    _: None = Depends(require_admin),
) -> dict:
    conv = brain.get_conversation(session, public_id, staff=True)
    if not conv:
        raise HTTPException(status_code=404, detail="Not found")
    if payload.status not in ("resolved", "closed"):
        raise HTTPException(status_code=400, detail="status must be resolved or closed")
    note = payload.resolution.strip()
    conv.status = (
        ShippingCaseStatus.resolved.value if payload.status == "resolved"
        else ShippingCaseStatus.closed.value
    )
    conv.resolved_at = utcnow()
    conv.updated_at = utcnow()
    session.add(conv)
    session.add(ShippingMessage(
        conversation_id=conv.id, role="human", body=note,
        meta={"resolver": user.email if user else "admin"},
    ))
    session.commit()
    governance.write_audit(
        session, conversation=conv, actor="human", decision=payload.status,
        actions=["human_resolve"], reason=note,
    )
    if conv.user_id:
        notify(
            session, conv.user_id, "shipping_resolved",
            "Your shipping case was updated",
            body=note[:200], link="/shipping",
        )
    return _conv_dict(session, conv, with_messages=True)

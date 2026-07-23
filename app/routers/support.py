"""AI Support OS API — customer chat + staff review queues."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..auth import get_current_user, is_staff, require_user
from ..database import get_session
from ..models import (
    SupportCaseStatus,
    SupportConversation,
    SupportMessage,
    User,
    utcnow,
)
from ..notify import notify
from .. import ratelimit
from ..routers.admin import require_admin
from ..support import brain, knowledge
from ..support import governance as gov
from ..support import actions

router = APIRouter(prefix="/api/support", tags=["support"])
admin_router = APIRouter(prefix="/api/admin/support", tags=["admin-support"])


class StartPayload(BaseModel):
    channel: str = Field(default="web", max_length=20)


class MessagePayload(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: Optional[str] = Field(default=None, max_length=48)


class ResolvePayload(BaseModel):
    resolution: str = Field(min_length=1, max_length=1000)
    status: str = Field(default="resolved")  # resolved | closed


class KbUpsert(BaseModel):
    slug: str
    title: str
    category: str = "faq"
    tags: list[str] = Field(default_factory=list)
    body: str
    rules: dict = Field(default_factory=dict)
    active: bool = True


def _conv_dict(
    session: Session,
    conv: SupportConversation,
    *,
    with_messages: bool = False,
    include_access_token: bool = False,
) -> dict:
    ctx = dict(conv.context or {})
    access_secret = ctx.pop("access_secret", None)
    d = {
        "id": conv.public_id,
        "status": conv.status,
        "intent": conv.intent,
        "confidence": conv.confidence,
        "tone": conv.tone,
        "queue": conv.queue,
        "order_id": conv.order_id,
        "workflow": conv.workflow,
        "workflow_step": conv.workflow_step,
        "entities": conv.entities or {},
        "context": ctx,
        "channel": conv.channel,
        "user_id": conv.user_id,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
        "resolved_at": conv.resolved_at.isoformat() if conv.resolved_at else None,
    }
    if include_access_token and access_secret and conv.user_id is None:
        d["access_token"] = access_secret
    if with_messages:
        d["messages"] = brain.messages_for(session, conv)
    return d


@router.post("/conversations")
def start_support(
    request: Request,
    payload: StartPayload | None = None,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
) -> dict:
    ip = ratelimit.client_ip(request)
    ratelimit.limiter.hit(
        f"support:start:{ip}",
        limit=ratelimit.SUPPORT_IP_LIMIT,
        window_seconds=ratelimit.SUPPORT_IP_WINDOW,
    )
    channel = (payload.channel if payload else "web") or "web"
    conv = brain.start_conversation(session, user=user, channel=channel)
    return {
        **_conv_dict(session, conv, with_messages=True, include_access_token=True),
        "reply": brain.messages_for(session, conv)[-1]["body"] if brain.messages_for(session, conv) else "",
        "chips": ["Track my order", "I need a refund", "How do fees work?", "I want to sell"],
    }


@router.get("/conversations/{public_id}")
def get_support_conversation(
    public_id: str,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
    x_support_token: str = Header(default="", alias="X-Support-Token"),
) -> dict:
    conv = brain.get_conversation(
        session, public_id, user=user, staff=is_staff(user), access_token=x_support_token,
    )
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return _conv_dict(session, conv, with_messages=True)


@router.post("/chat")
def support_chat(
    request: Request,
    payload: MessagePayload,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
    x_support_token: str = Header(default="", alias="X-Support-Token"),
) -> dict:
    """Main intake endpoint: send a message, get AI reply + actions taken."""
    ip = ratelimit.client_ip(request)
    ratelimit.limiter.hit(
        f"support:chat:{ip}",
        limit=ratelimit.SUPPORT_IP_LIMIT,
        window_seconds=ratelimit.SUPPORT_IP_WINDOW,
    )
    text = payload.message.strip()
    if payload.conversation_id:
        conv = brain.get_conversation(
            session,
            payload.conversation_id,
            user=user,
            staff=is_staff(user),
            access_token=x_support_token,
        )
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conv = brain.start_conversation(session, user=user, channel="web")

    # Special chip: talk to a human
    if text.lower().strip() in {"talk to a human", "human", "agent", "escalate"}:
        gov.escalate_conversation(
            session, conv, queue="general",
            reason="Customer requested human support",
        )
        actions.flag_human_review(session, conv, reason="Customer requested human")
        reply = ("I've moved you to a human review queue. A teammate will pick this up. "
                 "Your case id is " + conv.public_id + ".")
        brain.add_message(session, conv, "user", text)
        brain.add_message(session, conv, "assistant", reply, meta={"escalated": True})
        return {
            **_conv_dict(session, conv, include_access_token=True),
            "reply": reply,
            "decision": "escalate",
            "chips": [],
        }

    result = brain.handle_message(session, conv, text, user=user)
    return {
        **_conv_dict(session, conv, include_access_token=True),
        **result,
        "chips": result.get("chips") or [
            "Track my order", "I need a refund", "Talk to a human",
        ],
    }


@router.get("/knowledge")
def public_knowledge(
    q: str = Query(default="", max_length=200),
    session: Session = Depends(get_session),
) -> dict:
    if q.strip():
        return {"items": knowledge.search(session, q, limit=8)}
    return {"items": knowledge.list_articles(session)}


@router.get("/mine")
def my_support_cases(
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    rows = session.exec(
        select(SupportConversation)
        .where(SupportConversation.user_id == user.id)
        .order_by(SupportConversation.updated_at.desc())
        .limit(50)
    ).all()
    return {"items": [_conv_dict(session, c) for c in rows]}


# --------------------------- admin / governance --------------------------- #

@admin_router.get("/queue")
def admin_support_queue(
    queue: Optional[str] = None,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
) -> dict:
    rows = gov.list_queue(session, queue=queue, status=status_filter)
    return {"items": [_conv_dict(session, c, with_messages=True) for c in rows]}


@admin_router.get("/conversations/{public_id}")
def admin_get_conversation(
    public_id: str,
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
) -> dict:
    conv = brain.get_conversation(session, public_id, staff=True)
    if not conv:
        raise HTTPException(status_code=404, detail="Not found")
    audits = gov.list_audit(session, conversation_id=conv.id)
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
def admin_resolve(
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
        SupportCaseStatus.resolved.value if payload.status == "resolved"
        else SupportCaseStatus.closed.value
    )
    conv.resolved_at = utcnow()
    conv.updated_at = utcnow()
    session.add(conv)
    session.add(SupportMessage(
        conversation_id=conv.id, role="human", body=note,
        meta={"resolver": user.email if user else "admin"},
    ))
    session.commit()
    gov.write_audit(
        session, conversation=conv, actor="human", decision=payload.status,
        actions=["human_resolve"], reason=note,
    )
    if conv.user_id:
        notify(
            session, conv.user_id, "support_resolved",
            "Your support case was updated",
            body=note[:200], link="/account",
        )
    return _conv_dict(session, conv, with_messages=True)


@admin_router.get("/audit")
def admin_audit(
    conversation_id: Optional[int] = None,
    limit: int = Query(default=100, le=500),
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
) -> dict:
    rows = gov.list_audit(session, conversation_id=conversation_id, limit=limit)
    return {
        "items": [
            {
                "id": a.id,
                "conversation_id": a.conversation_id,
                "user_id": a.user_id,
                "order_id": a.order_id,
                "actor": a.actor,
                "intent": a.intent,
                "decision": a.decision,
                "actions": a.actions,
                "policy_refs": a.policy_refs,
                "confidence": a.confidence,
                "risk": a.risk,
                "reason": a.reason,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in rows
        ]
    }


@admin_router.get("/knowledge")
def admin_list_kb(
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
) -> dict:
    return {"items": knowledge.list_articles(session)}


@admin_router.put("/knowledge")
def admin_upsert_kb(
    payload: KbUpsert,
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
) -> dict:
    art = knowledge.upsert_article(session, payload.model_dump())
    return {
        "slug": art.slug, "title": art.title, "category": art.category,
        "tags": art.tags, "body": art.body, "rules": art.rules, "active": art.active,
    }

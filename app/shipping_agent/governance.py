"""Governance — confidence bands, audit trail, human queues for Dispatch."""
from __future__ import annotations

from typing import Optional

from sqlmodel import Session, select

from ..config import settings
from ..models import (
    ShippingAuditLog,
    ShippingCaseStatus,
    ShippingConversation,
    utcnow,
)
from .policy import PolicyDecision


def _conf_autonomous() -> float:
    return float(getattr(settings, "support_conf_autonomous", 0.90))


def _conf_review() -> float:
    return float(getattr(settings, "support_conf_review", 0.70))


def autonomy_band(confidence: float, risk: str) -> str:
    risk = (risk or "low").lower()
    if risk == "high" or confidence < _conf_review():
        return "escalate"
    if risk == "medium" or confidence < _conf_autonomous():
        return "flag_review"
    return "act"


def apply_governance(
    decision: PolicyDecision,
    *,
    confidence: float,
) -> PolicyDecision:
    band = autonomy_band(confidence, decision.risk)
    if decision.decision in ("deny", "clarify", "escalate", "inform"):
        if decision.decision == "escalate" and not decision.queue:
            decision.queue = "shipping"
        return decision

    if band == "escalate":
        decision.decision = "escalate"
        decision.queue = decision.queue or "shipping"
        if "flag_for_review" not in decision.actions:
            decision.actions = list(decision.actions) + ["flag_for_review"]
        decision.reason = (
            f"{decision.reason} — routed for human review "
            f"(confidence={confidence:.0%}, risk={decision.risk})."
        ).strip(" —")
        return decision

    if band == "flag_review":
        if "flag_for_review" not in decision.actions:
            decision.actions = list(decision.actions) + ["flag_for_review"]
        decision.detail = {**(decision.detail or {}), "post_action_review": True}
    return decision


def write_audit(
    session: Session,
    *,
    conversation: Optional[ShippingConversation] = None,
    user_id: Optional[int] = None,
    seller_id: Optional[int] = None,
    order_id: Optional[int] = None,
    actor: str = "ai",
    intent: Optional[str] = None,
    decision: Optional[str] = None,
    actions: Optional[list] = None,
    policy_refs: Optional[list] = None,
    confidence: Optional[float] = None,
    risk: Optional[str] = None,
    reason: Optional[str] = None,
    detail: Optional[dict] = None,
) -> ShippingAuditLog:
    row = ShippingAuditLog(
        conversation_id=conversation.id if conversation else None,
        user_id=user_id or (conversation.user_id if conversation else None),
        seller_id=seller_id or (conversation.seller_id if conversation else None),
        order_id=order_id or (conversation.order_id if conversation else None),
        actor=actor,
        intent=intent or (conversation.intent if conversation else None),
        decision=decision,
        actions=actions or [],
        policy_refs=policy_refs or [],
        confidence=confidence,
        risk=risk,
        reason=(reason or "")[:2000] or None,
        detail=detail or {},
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def escalate_conversation(
    session: Session,
    conv: ShippingConversation,
    *,
    queue: str = "shipping",
    reason: str = "",
) -> ShippingConversation:
    conv.status = ShippingCaseStatus.escalated.value
    conv.queue = queue
    ctx = dict(conv.context or {})
    ctx["escalation_reason"] = reason[:500]
    conv.context = ctx
    conv.updated_at = utcnow()
    session.add(conv)
    session.commit()
    session.refresh(conv)
    return conv


def list_queue(
    session: Session,
    *,
    queue: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> list[ShippingConversation]:
    q = select(ShippingConversation).order_by(ShippingConversation.updated_at.desc())
    rows = list(session.exec(q.limit(200)).all())
    out = []
    for c in rows:
        if queue and c.queue != queue:
            continue
        if status and c.status != status:
            continue
        if not status and c.status not in (
            ShippingCaseStatus.escalated.value,
            ShippingCaseStatus.pending_review.value,
        ):
            continue
        out.append(c)
        if len(out) >= limit:
            break
    return out


def list_audit(
    session: Session,
    *,
    conversation_id: Optional[int] = None,
    limit: int = 100,
) -> list[ShippingAuditLog]:
    q = select(ShippingAuditLog).order_by(ShippingAuditLog.created_at.desc())
    if conversation_id:
        q = q.where(ShippingAuditLog.conversation_id == conversation_id)
    return list(session.exec(q.limit(limit)).all())

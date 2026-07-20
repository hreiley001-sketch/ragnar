"""Governance layer — confidence thresholds, audit trail, human queues."""
from __future__ import annotations

from typing import Optional

from sqlmodel import Session, select

from ..config import settings
from ..models import (
    SupportAuditLog,
    SupportCaseStatus,
    SupportConversation,
    SupportQueue,
    utcnow,
)
from .policy import PolicyDecision

# Autonomy bands (overridable via env / settings).
def _conf_autonomous() -> float:
    return float(getattr(settings, "support_conf_autonomous", 0.90))


def _conf_review() -> float:
    return float(getattr(settings, "support_conf_review", 0.70))


def autonomy_band(confidence: float, risk: str) -> str:
    """Return act | flag_review | escalate."""
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
    """Possibly downgrade an approve into escalate/flag based on thresholds."""
    band = autonomy_band(confidence, decision.risk)
    if decision.decision in ("deny", "clarify", "escalate"):
        if decision.decision == "escalate" and not decision.queue:
            decision.queue = SupportQueue.general.value
        return decision

    if band == "escalate":
        decision.decision = "escalate"
        decision.queue = decision.queue or (
            SupportQueue.high_value.value if decision.risk == "high"
            else SupportQueue.general.value
        )
        if "flag_for_review" not in decision.actions:
            decision.actions = list(decision.actions) + ["flag_for_review"]
        decision.reason = (decision.reason + " — routed for human review "
                           f"(confidence={confidence:.0%}, risk={decision.risk}).").strip(" —")
        return decision

    if band == "flag_review":
        if "flag_for_review" not in decision.actions:
            decision.actions = list(decision.actions) + ["flag_for_review"]
        decision.detail = {**(decision.detail or {}), "post_action_review": True}
    return decision


def write_audit(
    session: Session,
    *,
    conversation: Optional[SupportConversation] = None,
    user_id: Optional[int] = None,
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
) -> SupportAuditLog:
    row = SupportAuditLog(
        conversation_id=conversation.id if conversation else None,
        user_id=user_id or (conversation.user_id if conversation else None),
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
    conv: SupportConversation,
    *,
    queue: str = SupportQueue.general.value,
    reason: str = "",
) -> SupportConversation:
    conv.status = SupportCaseStatus.escalated.value
    conv.queue = queue
    conv.updated_at = utcnow()
    ctx = dict(conv.context or {})
    ctx["escalation_reason"] = reason[:500]
    conv.context = ctx
    session.add(conv)
    session.commit()
    session.refresh(conv)
    write_audit(
        session, conversation=conv, actor="ai", decision="escalate",
        actions=["flag_for_review"], reason=reason, risk="high",
        detail={"queue": queue},
    )
    return conv


def list_queue(
    session: Session,
    *,
    queue: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[SupportConversation]:
    stmt = select(SupportConversation).order_by(SupportConversation.updated_at.desc())
    if queue:
        stmt = stmt.where(SupportConversation.queue == queue)
    if status:
        stmt = stmt.where(SupportConversation.status == status)
        rows = list(session.exec(stmt.limit(limit)).all())
    else:
        rows = list(session.exec(stmt.limit(limit * 3)).all())
        wanted = {
            SupportCaseStatus.escalated.value,
            SupportCaseStatus.pending_review.value,
        }
        rows = [r for r in rows if r.status in wanted][:limit]
    return rows


def list_audit(
    session: Session,
    *,
    conversation_id: int | None = None,
    limit: int = 100,
) -> list[SupportAuditLog]:
    stmt = select(SupportAuditLog).order_by(SupportAuditLog.created_at.desc())
    if conversation_id:
        stmt = stmt.where(SupportAuditLog.conversation_id == conversation_id)
    return list(session.exec(stmt.limit(limit)).all())

"""Workflow engine — state machines for refund / return / cancel / track."""
from __future__ import annotations

from typing import Optional

from sqlmodel import Session

from ..models import (
    Order,
    SupportCaseStatus,
    SupportConversation,
    User,
    utcnow,
)
from . import actions, governance, policy
from .policy import PolicyDecision


def _set_workflow(session: Session, conv: SupportConversation, name: str, step: str) -> None:
    conv.workflow = name
    conv.workflow_step = step
    conv.status = SupportCaseStatus.in_workflow.value
    conv.updated_at = utcnow()
    session.add(conv)
    session.commit()
    session.refresh(conv)


def run_track(
    session: Session,
    conv: SupportConversation,
    order: Order,
) -> dict:
    _set_workflow(session, conv, "track_order", "fetch_status")
    summary = actions.order_summary(session, order)
    _set_workflow(session, conv, "track_order", "done")
    conv.status = SupportCaseStatus.resolved.value
    conv.resolved_at = utcnow()
    session.add(conv)
    session.commit()
    governance.write_audit(
        session, conversation=conv, order_id=order.id,
        intent="track_order", decision="inform",
        actions=["fetch_order_status"], policy_refs=["order-tracking"],
        reason="Provided tracking / status to buyer.",
        confidence=conv.confidence, risk="low",
        detail=summary,
    )
    return {
        "decision": "inform",
        "order": summary,
        "actions_taken": ["fetch_order_status"],
        "policy_refs": ["order-tracking"],
    }


def run_refund(
    session: Session,
    conv: SupportConversation,
    order: Order,
    *,
    user: Optional[User],
    reason: str,
    amount_cents: Optional[int] = None,
    confidence: float = 0.9,
) -> dict:
    _set_workflow(session, conv, "process_refund", "confirm_order")
    decision = policy.evaluate_refund(
        session, order=order, user_id=user.id if user else None,
        reason=reason, amount_cents=amount_cents,
    )
    decision = governance.apply_governance(decision, confidence=confidence)
    _set_workflow(session, conv, "process_refund", "policy_check")

    result: dict = {
        "decision": decision.decision,
        "policy": decision.as_dict(),
        "order": actions.order_summary(session, order),
        "actions_taken": [],
    }

    if decision.decision == "deny":
        _finish(session, conv, decision, confidence, order_id=order.id)
        return result

    if decision.decision == "escalate":
        actions.flag_human_review(session, conv, reason=decision.reason)
        if "open_dispute" in decision.actions:
            d = actions.open_dispute(
                session, order, user_id=user.id if user else None, reason=reason,
            )
            result["actions_taken"].append("open_dispute")
            result["dispute"] = d
        governance.escalate_conversation(
            session, conv, queue=decision.queue or "general", reason=decision.reason,
        )
        result["actions_taken"].append("flag_for_review")
        return result

    # approve / partial — execute.
    _set_workflow(session, conv, "process_refund", "execute")
    if decision.require_return and not decision.keep_item:
        label = actions.create_return_label(session, order)
        ctx = dict(conv.context or {})
        ctx["return_label"] = label
        conv.context = ctx
        session.add(conv)
        session.commit()
        result["return_label"] = label
        result["actions_taken"].append("create_return_label")
        # For MVP we still issue refund immediately when AI is allowed to act;
        # label is generated for the buyer. Flag for review if medium risk.
    refund = actions.issue_refund(
        session, order,
        amount_cents=decision.amount_cents or (order.price_cents + (order.shipping_cents or 0)),
        reason=reason or decision.reason,
        conversation=conv,
        kind="partial" if decision.decision == "partial" else "full",
    )
    result["refund"] = refund
    if not refund.get("ok", True):
        actions.flag_human_review(
            session, conv,
            reason=refund.get("error") or "Stripe refund failed — needs human",
        )
        result["actions_taken"].append("refund_failed_flag_review")
        result["decision"] = "escalate"
        governance.escalate_conversation(
            session, conv, queue="payments",
            reason=refund.get("error") or "Refund failed",
        )
        return result
    result["actions_taken"].append(
        "issue_partial_refund" if decision.decision == "partial" else "issue_refund"
    )
    result["order"] = actions.order_summary(session, order)

    if "flag_for_review" in decision.actions:
        conv.status = SupportCaseStatus.pending_review.value
        conv.queue = conv.queue or "general"
        actions.flag_human_review(session, conv, reason="Post-action review flag")
        result["actions_taken"].append("flag_for_review")
    else:
        conv.status = SupportCaseStatus.resolved.value
        conv.resolved_at = utcnow()
    conv.workflow_step = "done"
    conv.updated_at = utcnow()
    session.add(conv)
    session.commit()

    governance.write_audit(
        session, conversation=conv, order_id=order.id,
        intent="process_refund", decision=decision.decision,
        actions=result["actions_taken"], policy_refs=decision.policy_refs,
        confidence=confidence, risk=decision.risk, reason=decision.reason,
        detail={"refund": refund, "require_return": decision.require_return},
    )
    return result


def run_return(
    session: Session,
    conv: SupportConversation,
    order: Order,
    *,
    user: Optional[User],
    reason: str,
    confidence: float = 0.9,
) -> dict:
    _set_workflow(session, conv, "process_return", "validate")
    decision = policy.evaluate_return(session, order=order, reason=reason)
    decision = governance.apply_governance(decision, confidence=confidence)
    result: dict = {
        "decision": decision.decision,
        "policy": decision.as_dict(),
        "order": actions.order_summary(session, order),
        "actions_taken": [],
    }
    if decision.decision in ("deny", "escalate"):
        if decision.decision == "escalate":
            actions.flag_human_review(session, conv, reason=decision.reason)
            governance.escalate_conversation(
                session, conv, queue=decision.queue or "general", reason=decision.reason,
            )
            result["actions_taken"].append("flag_for_review")
        else:
            _finish(session, conv, decision, confidence, order_id=order.id)
        return result

    if decision.keep_item:
        refund = actions.issue_refund(
            session, order,
            amount_cents=decision.amount_cents or 0,
            reason=reason or "Keep-item refund",
            conversation=conv,
        )
        result["refund"] = refund
        if not refund.get("ok", True):
            actions.flag_human_review(session, conv, reason=refund.get("error") or "Refund failed")
            result["actions_taken"].append("refund_failed_flag_review")
            result["decision"] = "escalate"
            return result
        result["actions_taken"].append("issue_refund")
    else:
        label = actions.create_return_label(session, order)
        ctx = dict(conv.context or {})
        ctx["return_label"] = label
        conv.context = ctx
        result["return_label"] = label
        result["actions_taken"].append("create_return_label")

    conv.status = SupportCaseStatus.resolved.value
    conv.resolved_at = utcnow()
    conv.workflow_step = "done"
    conv.updated_at = utcnow()
    session.add(conv)
    session.commit()
    governance.write_audit(
        session, conversation=conv, order_id=order.id,
        intent="process_return", decision=decision.decision,
        actions=result["actions_taken"], policy_refs=decision.policy_refs,
        confidence=confidence, risk=decision.risk, reason=decision.reason,
        detail=result.get("return_label") or result.get("refund") or {},
    )
    return result


def run_cancel(
    session: Session,
    conv: SupportConversation,
    order: Order,
    *,
    user: Optional[User],
    reason: str,
    confidence: float = 0.9,
) -> dict:
    _set_workflow(session, conv, "cancel_order", "check")
    decision = policy.evaluate_cancel(order=order)
    decision = governance.apply_governance(decision, confidence=confidence)
    result: dict = {
        "decision": decision.decision,
        "policy": decision.as_dict(),
        "order": actions.order_summary(session, order),
        "actions_taken": [],
    }
    if decision.decision != "approve":
        _finish(session, conv, decision, confidence, order_id=order.id)
        return result

    actions.cancel_order(session, order)
    result["actions_taken"].append("cancel_order")
    refund = actions.issue_refund(
        session, order,
        amount_cents=decision.amount_cents or 0,
        reason=reason or "Buyer cancellation",
        conversation=conv,
    )
    result["refund"] = refund
    if not refund.get("ok", True):
        actions.flag_human_review(session, conv, reason=refund.get("error") or "Refund failed")
        result["actions_taken"].append("refund_failed_flag_review")
        result["decision"] = "escalate"
        return result
    result["actions_taken"].append("issue_refund")
    result["order"] = actions.order_summary(session, order)
    conv.status = SupportCaseStatus.resolved.value
    conv.resolved_at = utcnow()
    conv.workflow_step = "done"
    conv.updated_at = utcnow()
    session.add(conv)
    session.commit()
    governance.write_audit(
        session, conversation=conv, order_id=order.id,
        intent="cancel_order", decision="approve",
        actions=result["actions_taken"], policy_refs=decision.policy_refs,
        confidence=confidence, risk=decision.risk, reason=decision.reason,
        detail={"refund": refund},
    )
    return result


def _finish(
    session: Session,
    conv: SupportConversation,
    decision: PolicyDecision,
    confidence: float,
    *,
    order_id: Optional[int] = None,
) -> None:
    conv.workflow_step = "done"
    conv.status = (
        SupportCaseStatus.resolved.value
        if decision.decision == "deny"
        else SupportCaseStatus.awaiting_user.value
    )
    conv.updated_at = utcnow()
    session.add(conv)
    session.commit()
    governance.write_audit(
        session, conversation=conv, order_id=order_id,
        intent=conv.intent, decision=decision.decision,
        actions=decision.actions, policy_refs=decision.policy_refs,
        confidence=confidence, risk=decision.risk, reason=decision.reason,
    )

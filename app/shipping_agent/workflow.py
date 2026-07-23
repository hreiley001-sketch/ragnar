"""Workflow engine — quote / pack / label / ship / track / exception."""
from __future__ import annotations

from typing import Optional

from sqlmodel import Session

from ..models import Order, ShippingCaseStatus, ShippingConversation, utcnow
from .. import shipping as ship
from . import actions, governance, policy


def _set_workflow(session: Session, conv: ShippingConversation, name: str, step: str) -> None:
    conv.workflow = name
    conv.workflow_step = step
    conv.status = ShippingCaseStatus.in_workflow.value
    conv.updated_at = utcnow()
    session.add(conv)
    session.commit()
    session.refresh(conv)


def run_quote(
    session: Session,
    conv: ShippingConversation,
    order: Order,
    *,
    prefer: str = "balanced",
    confidence: float = 0.9,
) -> dict:
    _set_workflow(session, conv, "quote_rates", "fetch")
    quote = actions.quote_for_order(session, order, conv, prefer=prefer)
    conv.workflow_step = "done"
    conv.status = ShippingCaseStatus.resolved.value
    conv.resolved_at = utcnow()
    ctx = dict(conv.context or {})
    ctx["last_quote"] = {
        "recommended": quote.get("recommended"),
        "packaging": quote.get("packaging"),
        "insurance_cents": quote.get("insurance_cents"),
    }
    conv.context = ctx
    session.add(conv)
    session.commit()
    governance.write_audit(
        session, conversation=conv, order_id=order.id,
        intent="quote_rates", decision="inform",
        actions=["quote_rates", "recommend_packaging", "recommend_rate"],
        policy_refs=["rate-shopping", "card-packing"],
        reason="Quoted rates and recommended service.",
        confidence=confidence, risk="low", detail=quote.get("recommended") or {},
    )
    return {
        "decision": "inform",
        "quote": quote,
        "actions_taken": ["quote_rates", "recommend_rate"],
        "policy_refs": ["rate-shopping"],
    }


def run_packaging(
    session: Session,
    conv: ShippingConversation,
    *,
    order: Optional[Order] = None,
    is_graded: bool = False,
    value_cents: int = 0,
    confidence: float = 0.9,
) -> dict:
    value = value_cents or (order.price_cents if order else 0)
    if order and order.listing_id and is_graded is False:
        # Prefer listing truth when available and caller didn't force.
        from ..models import Listing
        listing = session.get(Listing, order.listing_id)
        if listing is not None:
            is_graded = bool(listing.is_graded)
    pack = ship.recommend_packaging(is_graded=is_graded, quantity=1, value_cents=value)
    insure = policy.insurance_advice(value_cents=value)
    governance.write_audit(
        session, conversation=conv, order_id=order.id if order else None,
        intent="recommend_packaging", decision="inform",
        actions=["recommend_packaging"],
        policy_refs=["card-packing"],
        reason=pack["label"],
        confidence=confidence, risk="low", detail=pack,
    )
    conv.status = ShippingCaseStatus.resolved.value
    conv.resolved_at = utcnow()
    conv.workflow = "recommend_packaging"
    conv.workflow_step = "done"
    session.add(conv)
    session.commit()
    return {
        "decision": "inform",
        "packaging": pack,
        "insurance": insure,
        "actions_taken": ["recommend_packaging"],
        "policy_refs": ["card-packing"],
    }


def run_label(
    session: Session,
    conv: ShippingConversation,
    order: Order,
    *,
    prefer: str = "balanced",
    confidence: float = 0.9,
    auto_ship: bool = True,
) -> dict:
    _set_workflow(session, conv, "create_label", "policy")
    decision = policy.evaluate_label(order=order)
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
                session, conv, queue=decision.queue or "shipping", reason=decision.reason,
            )
            result["actions_taken"].append("flag_for_review")
        else:
            conv.workflow_step = "done"
            conv.status = ShippingCaseStatus.resolved.value
            conv.resolved_at = utcnow()
            session.add(conv)
            session.commit()
        governance.write_audit(
            session, conversation=conv, order_id=order.id,
            intent="create_label", decision=decision.decision,
            actions=result["actions_taken"], policy_refs=decision.policy_refs,
            confidence=confidence, risk=decision.risk, reason=decision.reason,
        )
        return result

    _set_workflow(session, conv, "create_label", "purchase")
    label = actions.purchase_label(session, order, conv, prefer=prefer)
    result["label"] = label
    result["actions_taken"].append("create_label")
    ctx = dict(conv.context or {})
    ctx["last_label"] = label
    conv.context = ctx

    if auto_ship and label.get("tracking_number"):
        shipped = actions.mark_shipped(
            session, order,
            tracking_number=label["tracking_number"],
            carrier=label.get("carrier"),
        )
        result["order"] = shipped
        result["actions_taken"].append("mark_shipped")

    if "flag_for_review" in decision.actions:
        conv.status = ShippingCaseStatus.pending_review.value
        actions.flag_human_review(session, conv, reason="High-value label — post-action review")
        result["actions_taken"].append("flag_for_review")
    else:
        conv.status = ShippingCaseStatus.resolved.value
        conv.resolved_at = utcnow()
    conv.workflow_step = "done"
    conv.updated_at = utcnow()
    session.add(conv)
    session.commit()
    governance.write_audit(
        session, conversation=conv, order_id=order.id,
        intent="create_label", decision="approve",
        actions=result["actions_taken"], policy_refs=decision.policy_refs,
        confidence=confidence, risk=decision.risk, reason=decision.reason,
        detail={"label_id": label.get("label_id"), "tracking": label.get("tracking_number")},
    )
    return result


def run_ship(
    session: Session,
    conv: ShippingConversation,
    order: Order,
    *,
    tracking_number: str,
    carrier: str | None = None,
    confidence: float = 0.9,
) -> dict:
    _set_workflow(session, conv, "ship_order", "check")
    decision = policy.evaluate_ship(order=order, tracking_number=tracking_number)
    decision = governance.apply_governance(decision, confidence=confidence)
    result: dict = {
        "decision": decision.decision,
        "policy": decision.as_dict(),
        "actions_taken": [],
    }
    if decision.decision != "approve":
        conv.workflow_step = "done"
        conv.status = ShippingCaseStatus.awaiting_user.value
        session.add(conv)
        session.commit()
        return result
    carrier = carrier or ship.detect_carrier(tracking_number)
    summary = actions.mark_shipped(
        session, order, tracking_number=tracking_number, carrier=carrier,
    )
    result["order"] = summary
    result["actions_taken"].append("mark_shipped")
    conv.status = ShippingCaseStatus.resolved.value
    conv.resolved_at = utcnow()
    conv.workflow_step = "done"
    session.add(conv)
    session.commit()
    governance.write_audit(
        session, conversation=conv, order_id=order.id,
        intent="ship_order", decision="approve",
        actions=result["actions_taken"], policy_refs=decision.policy_refs,
        confidence=confidence, risk="low", reason=decision.reason,
        detail=summary,
    )
    return result


def run_track(
    session: Session,
    conv: ShippingConversation,
    *,
    order: Optional[Order] = None,
    tracking_number: str | None = None,
    carrier: str | None = None,
    confidence: float = 0.9,
) -> dict:
    number = tracking_number or (order.tracking_number if order else None)
    carr = carrier or (order.carrier if order else None)
    status = ship.track_status(carr, number)
    conv.workflow = "track_shipment"
    conv.workflow_step = "done"
    conv.status = ShippingCaseStatus.resolved.value
    conv.resolved_at = utcnow()
    session.add(conv)
    session.commit()
    governance.write_audit(
        session, conversation=conv, order_id=order.id if order else None,
        intent="track_shipment", decision="inform",
        actions=["fetch_tracking"], policy_refs=["order-tracking"],
        reason="Provided tracking status.",
        confidence=confidence, risk="low", detail=status,
    )
    return {
        "decision": "inform",
        "tracking": status,
        "order": actions.order_summary(session, order) if order else None,
        "actions_taken": ["fetch_tracking"],
        "policy_refs": ["order-tracking"],
    }


def run_exception(
    session: Session,
    conv: ShippingConversation,
    order: Order,
    *,
    reason: str,
    confidence: float = 0.9,
) -> dict:
    decision = policy.evaluate_exception(order=order, reason=reason)
    decision = governance.apply_governance(decision, confidence=confidence)
    result: dict = {
        "decision": decision.decision,
        "policy": decision.as_dict(),
        "order": actions.order_summary(session, order),
        "tracking": ship.track_status(order.carrier, order.tracking_number),
        "actions_taken": [],
    }
    if decision.decision == "escalate":
        actions.flag_human_review(session, conv, reason=decision.reason)
        governance.escalate_conversation(
            session, conv, queue=decision.queue or "shipping", reason=decision.reason,
        )
        result["actions_taken"].append("flag_for_review")
    else:
        conv.status = ShippingCaseStatus.resolved.value
        conv.resolved_at = utcnow()
        session.add(conv)
        session.commit()
        result["actions_taken"].append("fetch_tracking")
    governance.write_audit(
        session, conversation=conv, order_id=order.id,
        intent="handle_exception", decision=decision.decision,
        actions=result["actions_taken"], policy_refs=decision.policy_refs,
        confidence=confidence, risk=decision.risk, reason=decision.reason,
    )
    return result


def run_to_ship(
    session: Session,
    conv: ShippingConversation,
    *,
    seller_id: Optional[int],
    confidence: float = 0.9,
) -> dict:
    orders = actions.list_to_ship(session, seller_id=seller_id, limit=15)
    items = [actions.order_summary(session, o) for o in orders]
    conv.workflow = "list_to_ship"
    conv.workflow_step = "done"
    conv.status = ShippingCaseStatus.resolved.value
    conv.resolved_at = utcnow()
    session.add(conv)
    session.commit()
    governance.write_audit(
        session, conversation=conv,
        intent="list_to_ship", decision="inform",
        actions=["list_to_ship"], policy_refs=["fulfillment-sla"],
        reason=f"{len(items)} order(s) awaiting shipment.",
        confidence=confidence, risk="low", detail={"count": len(items)},
    )
    return {
        "decision": "inform",
        "to_ship": items,
        "actions_taken": ["list_to_ship"],
        "policy_refs": ["fulfillment-sla"],
    }

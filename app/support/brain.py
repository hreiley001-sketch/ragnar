"""AI Brain — orchestrates intake → policy → workflow → reply.

Conversation memory lives on SupportConversation + SupportMessage.
Tone adapts: normal / frustrated / high_risk.
"""
from __future__ import annotations

import secrets
from typing import Optional

from sqlmodel import Session, select

from ..models import (
    SupportCaseStatus,
    SupportChannel,
    SupportConversation,
    SupportMessage,
    User,
    utcnow,
)
from . import actions, governance, intent, knowledge, policy, workflow


def _public_id() -> str:
    return "sup_" + secrets.token_hex(6)


def start_conversation(
    session: Session,
    *,
    user: Optional[User] = None,
    channel: str = SupportChannel.web.value,
) -> SupportConversation:
    knowledge.ensure_knowledge(session)
    conv = SupportConversation(
        public_id=_public_id(),
        user_id=user.id if user else None,
        channel=channel,
        status=SupportCaseStatus.open.value,
    )
    session.add(conv)
    session.commit()
    session.refresh(conv)
    welcome = (
        "I'm RAGNAR Support — I can track orders, handle refunds and returns, "
        "explain fees, and help with seller onboarding. What do you need?"
    )
    _add_msg(session, conv, "assistant", welcome, meta={"kind": "welcome"})
    return conv


def get_conversation(
    session: Session,
    public_id: str,
    *,
    user: Optional[User] = None,
    staff: bool = False,
) -> Optional[SupportConversation]:
    conv = session.exec(
        select(SupportConversation).where(SupportConversation.public_id == public_id)
    ).first()
    if not conv:
        return None
    if staff:
        return conv
    if user and conv.user_id and conv.user_id != user.id:
        return None
    if user and conv.user_id is None:
        # Claim anonymous thread on first authenticated message.
        conv.user_id = user.id
        session.add(conv)
        session.commit()
        session.refresh(conv)
    return conv


def messages_for(session: Session, conv: SupportConversation) -> list[dict]:
    rows = session.exec(
        select(SupportMessage)
        .where(SupportMessage.conversation_id == conv.id)
        .order_by(SupportMessage.created_at.asc())
    ).all()
    return [
        {
            "id": m.id,
            "role": m.role,
            "body": m.body,
            "meta": m.meta or {},
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in rows
    ]


def _add_msg(
    session: Session,
    conv: SupportConversation,
    role: str,
    body: str,
    *,
    meta: dict | None = None,
) -> SupportMessage:
    msg = SupportMessage(
        conversation_id=conv.id,
        role=role,
        body=body[:4000],
        meta=meta or {},
    )
    conv.updated_at = utcnow()
    session.add(msg)
    session.add(conv)
    session.commit()
    session.refresh(msg)
    return msg


def add_message(
    session: Session,
    conv: SupportConversation,
    role: str,
    body: str,
    *,
    meta: dict | None = None,
) -> SupportMessage:
    return _add_msg(session, conv, role, body, meta=meta)


def handle_message(
    session: Session,
    conv: SupportConversation,
    text: str,
    *,
    user: Optional[User] = None,
) -> dict:
    text = (text or "").strip()
    if not text:
        return _pack(conv, session, "Please tell me what you need help with.", {})

    _add_msg(session, conv, "user", text)
    knowledge.ensure_knowledge(session)

    intake = intent.classify(text, prior_entities=conv.entities or {})
    conv.intent = intake.intent
    conv.confidence = intake.confidence
    conv.tone = intake.tone
    conv.entities = intake.entities
    if intake.entities.get("order_id"):
        conv.order_id = intake.entities["order_id"]
    conv.updated_at = utcnow()
    session.add(conv)
    session.commit()
    session.refresh(conv)

    # Medium confidence → clarify before acting.
    if intake.clarifying_question and (
        intake.confidence < 0.7
        or (
            intake.intent in {
                "process_refund", "process_return", "cancel_order",
                "report_item_not_received", "report_not_as_described", "track_order",
            }
            and not intake.entities.get("order_id")
        )
    ):
        reply = _tone(intake.tone, intake.clarifying_question)
        chips = _chips_for(intake.intent, user, session)
        _add_msg(session, conv, "assistant", reply, meta={
            "intent": intake.intent, "confidence": intake.confidence, "clarify": True,
        })
        return _pack(conv, session, reply, {
            "intent": intake.intent,
            "confidence": intake.confidence,
            "tone": intake.tone,
            "entities": intake.entities,
            "chips": chips,
            "status": "awaiting_user",
        })

    # Route by intent.
    if intake.intent == "greeting":
        reply = _tone(intake.tone,
            "Hey — I can track an order, start a refund or return, cancel before ship, "
            "or answer fee / seller questions. What's going on?")
        _add_msg(session, conv, "assistant", reply)
        return _pack(conv, session, reply, {
            "intent": "greeting", "confidence": intake.confidence,
            "chips": ["Track my order", "I need a refund", "How do fees work?",
                      "I want to sell on RAGNAR"],
        })

    if intake.intent in ("fees_question", "seller_onboarding_question", "policy_question"):
        return _answer_from_kb(session, conv, text, intake)

    if intake.intent == "account_security_issue":
        decision = policy.evaluate_security(message=text)
        governance.apply_governance(decision, confidence=intake.confidence)
        actions.flag_human_review(session, conv, reason=decision.reason)
        governance.escalate_conversation(
            session, conv, queue=decision.queue or "fraud", reason=decision.reason,
        )
        reply = _tone("high_risk",
            "This sounds like an account security issue. I've flagged it for our "
            "security queue. Meanwhile: change your password and revoke other sessions "
            "from Account settings. A human will follow up.")
        _add_msg(session, conv, "assistant", reply, meta={"escalated": True})
        return _pack(conv, session, reply, {
            "intent": intake.intent, "decision": "escalate", "queue": "fraud",
        })

    # Order-bound workflows.
    if intake.intent in {
        "track_order", "process_refund", "process_return", "cancel_order",
        "report_item_not_received", "report_not_as_described",
    }:
        return _order_workflow(session, conv, text, intake, user)

    # Fallback: KB search.
    return _answer_from_kb(session, conv, text, intake)


def _order_workflow(session, conv, text, intake, user) -> dict:
    order_id = intake.entities.get("order_id") or conv.order_id
    if not order_id:
        reply = _tone(
            intake.tone,
            intent.clarify_for(intake.intent, {})
            or "What's your order number?",
        )
        _add_msg(session, conv, "assistant", reply, meta={"clarify": True})
        return _pack(conv, session, reply, {"status": "awaiting_user", "chips": []})

    order = actions.get_buyer_order(
        session, int(order_id), user_id=user.id if user else None,
    )
    if not order:
        # Not signed in or not their order — still allow track info? No: privacy.
        if not user:
            reply = ("Sign in so I can look up order "
                     f"#{order_id} securely, or paste details from your confirmation email.")
        else:
            # Try listing their recent orders to help.
            recent = actions.list_buyer_orders(session, user.id, limit=5)
            if recent:
                bits = ", ".join(f"#{o.id} ({o.title[:40]})" for o in recent)
                reply = (f"I couldn't match order #{order_id} to your account. "
                         f"Your recent orders: {bits}. Which one?")
            else:
                reply = (f"I couldn't find order #{order_id} on your account. "
                         "Double-check the number under Account → Orders.")
        _add_msg(session, conv, "assistant", reply, meta={"clarify": True})
        return _pack(conv, session, reply, {"status": "awaiting_user"})

    conv.order_id = order.id
    session.add(conv)
    session.commit()

    reason = intake.entities.get("reason_hint") or text
    amount_cents = intake.entities.get("amount_cents")
    conf = float(intake.confidence or 0.8)

    # Map not-received / NAD into refund path with enriched reason.
    wf_intent = intake.intent
    if wf_intent == "report_item_not_received":
        reason = "item not received: " + reason
        wf_intent = "process_refund"
    elif wf_intent == "report_not_as_described":
        reason = "not as described: " + reason
        wf_intent = "process_refund"

    if wf_intent == "track_order":
        result = workflow.run_track(session, conv, order)
        summary = result["order"]
        track = summary.get("tracking_url") or summary.get("tracking_number")
        if summary["status"] == "shipped" and track:
            body = (f"Order #{summary['id']} — **{summary['title']}** is "
                    f"**shipped** via {summary.get('carrier') or 'carrier'}. "
                    f"Tracking: {summary.get('tracking_number')}"
                    + (f" ([track]({summary['tracking_url']}))" if summary.get("tracking_url") else "")
                    + ".")
        else:
            body = (f"Order #{summary['id']} — **{summary['title']}** is "
                    f"**{summary['status']}**. Total ${summary['total']:.2f}.")
        reply = _tone(intake.tone, _strip_md(body) + " " + _next_steps(result))
        _add_msg(session, conv, "assistant", reply, meta={"workflow": result})
        return _pack(conv, session, reply, {
            "intent": "track_order", "workflow": result, "confidence": conf,
        })

    if wf_intent == "process_refund":
        result = workflow.run_refund(
            session, conv, order, user=user, reason=reason,
            amount_cents=amount_cents, confidence=conf,
        )
        reply = _refund_reply(intake.tone, result)
        _add_msg(session, conv, "assistant", reply, meta={"workflow": result})
        return _pack(conv, session, reply, {
            "intent": "process_refund", "workflow": result, "confidence": conf,
        })

    if wf_intent == "process_return":
        result = workflow.run_return(
            session, conv, order, user=user, reason=reason, confidence=conf,
        )
        reply = _return_reply(intake.tone, result)
        _add_msg(session, conv, "assistant", reply, meta={"workflow": result})
        return _pack(conv, session, reply, {
            "intent": "process_return", "workflow": result, "confidence": conf,
        })

    if wf_intent == "cancel_order":
        result = workflow.run_cancel(
            session, conv, order, user=user, reason=reason, confidence=conf,
        )
        reply = _cancel_reply(intake.tone, result)
        _add_msg(session, conv, "assistant", reply, meta={"workflow": result})
        return _pack(conv, session, reply, {
            "intent": "cancel_order", "workflow": result, "confidence": conf,
        })

    return _answer_from_kb(session, conv, text, intake)


def _answer_from_kb(session, conv, text, intake) -> dict:
    hits = knowledge.search(session, text, limit=3)
    if not hits:
        # Intent-specific slug fallbacks.
        slug_map = {
            "fees_question": "fees-faq",
            "seller_onboarding_question": "seller-onboarding",
            "policy_question": "buyer-protection",
        }
        slug = slug_map.get(intake.intent)
        if slug:
            art = knowledge.get_by_slug(session, slug)
            if art:
                hits = [{
                    "slug": art.slug, "title": art.title, "body": art.body,
                    "category": art.category, "score": 1,
                }]
    if hits:
        top = hits[0]
        reply = _tone(intake.tone,
            f"{top['body']}\n\n"
            f"Here's what I've done for you: answered from our “{top['title']}” policy. "
            "Want me to start a refund, return, or tracking lookup next?")
        refs = [h["slug"] for h in hits]
        governance.write_audit(
            session, conversation=conv, intent=intake.intent, decision="inform",
            actions=["kb_retrieve"], policy_refs=refs,
            confidence=intake.confidence, risk="low",
            reason=f"Grounded answer from {top['slug']}",
        )
        _add_msg(session, conv, "assistant", reply, meta={"kb": refs})
        return _pack(conv, session, reply, {
            "intent": intake.intent, "kb": hits,
            "chips": ["Track my order", "I need a refund", "Return an item"],
        })

    reply = _tone(intake.tone,
        "I'm not fully sure I have that covered. I can help with refunds, returns, "
        "tracking, cancellations, fees, and seller onboarding — or escalate to a human.")
    _add_msg(session, conv, "assistant", reply)
    return _pack(conv, session, reply, {
        "intent": intake.intent or "other",
        "chips": ["Talk to a human", "Track my order", "Refund help"],
    })


def _refund_reply(tone: str, result: dict) -> str:
    d = result.get("decision")
    order = result.get("order") or {}
    if d == "deny":
        reason = (result.get("policy") or {}).get("reason") or "Not eligible under policy."
        return _tone(tone, f"I can't issue a refund on order #{order.get('id')}. {reason}")
    if d == "escalate":
        reason = (result.get("policy") or {}).get("reason") or "Needs human review."
        return _tone(tone if tone == "high_risk" else "frustrated",
            f"I've escalated order #{order.get('id')} for human review. {reason} "
            "You'll get an update in Account notifications.")
    refund = result.get("refund") or {}
    amt = refund.get("amount")
    bits = [f"Here's what I've done for you on order #{order.get('id')} ({order.get('title')}):"]
    if "create_return_label" in result.get("actions_taken", []):
        label = result.get("return_label") or {}
        bits.append(f"Created return label {label.get('label_id')} "
                    f"(tracking {label.get('tracking_number')}).")
    if amt is not None:
        when = "You'll see the refund in 3–5 business days" if refund.get("status") == "stripe_refunded" \
            else "Refund is recorded; Stripe payout timing applies once processing completes"
        bits.append(f"Issued a ${amt:.2f} refund. {when}.")
    if (result.get("policy") or {}).get("keep_item"):
        bits.append("You don't need to send the item back.")
    if "flag_for_review" in result.get("actions_taken", []):
        bits.append("I flagged this for a quick later review (medium confidence/risk).")
    return _tone(tone, " ".join(bits))


def _return_reply(tone: str, result: dict) -> str:
    d = result.get("decision")
    order = result.get("order") or {}
    if d == "deny":
        return _tone(tone, f"I can't start a return on order #{order.get('id')}. "
                     f"{(result.get('policy') or {}).get('reason', '')}")
    if d == "escalate":
        return _tone(tone, "I've sent this return case to a human queue for review.")
    if result.get("return_label"):
        label = result["return_label"]
        return _tone(tone,
            f"Return approved for order #{order.get('id')}. "
            f"Label {label.get('label_id')} is ready — tracking {label.get('tracking_number')}. "
            "Refund triggers when the return is scanned.")
    if result.get("refund"):
        return _tone(tone,
            f"You can keep the item. I've refunded "
            f"${result['refund'].get('amount', 0):.2f} on order #{order.get('id')}.")
    return _tone(tone, "Return request processed.")


def _cancel_reply(tone: str, result: dict) -> str:
    d = result.get("decision")
    order = result.get("order") or {}
    if d != "approve":
        return _tone(tone, f"I couldn't cancel order #{order.get('id')}. "
                     f"{(result.get('policy') or {}).get('reason', '')}")
    amt = (result.get("refund") or {}).get("amount")
    return _tone(tone,
        f"Cancelled order #{order.get('id')}. "
        + (f"Refund of ${amt:.2f} is on the way." if amt is not None else ""))


def _next_steps(result: dict) -> str:
    return "Confirm next steps anytime — refund, return, or cancel if something's wrong."


def _tone(tone: str, text: str) -> str:
    text = text.strip()
    if tone == "frustrated":
        return ("I hear you — sorry this has been frustrating. " + text)
    if tone == "high_risk":
        return text  # serious, no fluff
    return text


def _strip_md(s: str) -> str:
    return s.replace("**", "")


def _chips_for(intent_name: str, user: Optional[User], session: Session) -> list[str]:
    chips = []
    if user:
        orders = actions.list_buyer_orders(session, user.id, limit=3)
        for o in orders:
            chips.append(f"Order #{o.id}")
    if intent_name in ("process_refund", "other"):
        chips += ["I need a refund", "Item not received"]
    if intent_name == "track_order":
        chips += ["Where is my package?"]
    return chips[:4]


def _pack(conv: SupportConversation, session: Session, reply: str, extra: dict) -> dict:
    session.refresh(conv)
    return {
        "conversation_id": conv.public_id,
        "status": conv.status,
        "intent": conv.intent,
        "confidence": conv.confidence,
        "tone": conv.tone,
        "queue": conv.queue,
        "reply": reply,
        "entities": conv.entities or {},
        "workflow": conv.workflow,
        "workflow_step": conv.workflow_step,
        **extra,
    }


# Late import helper used above — expose clarify without circular fuss.
# (intent module already imported)

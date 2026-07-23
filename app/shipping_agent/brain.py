"""Dispatch brain — intake → policy → workflow → reply."""
from __future__ import annotations

import secrets
from typing import Optional

from sqlmodel import Session, select

from ..auth import is_staff
from ..models import (
    Seller,
    ShippingCaseStatus,
    ShippingConversation,
    ShippingMessage,
    User,
    utcnow,
)
from . import actions, governance, intent, knowledge, workflow


def _public_id() -> str:
    return "shp_" + secrets.token_hex(6)


def _seller_for_user(session: Session, user: Optional[User]) -> Optional[Seller]:
    if not user or not user.email:
        return None
    return session.exec(
        select(Seller).where(Seller.email == user.email)
    ).first()


def start_conversation(
    session: Session,
    *,
    user: Optional[User] = None,
    channel: str = "web",
    seller_id: Optional[int] = None,
) -> ShippingConversation:
    knowledge.ensure_knowledge(session)
    seller = None
    if seller_id:
        seller = session.get(Seller, seller_id)
    elif user:
        seller = _seller_for_user(session, user)
    conv = ShippingConversation(
        public_id=_public_id(),
        user_id=user.id if user else None,
        seller_id=seller.id if seller else seller_id,
        channel=channel,
        status=ShippingCaseStatus.open.value,
    )
    session.add(conv)
    session.commit()
    session.refresh(conv)
    _add_msg(session, conv, "assistant", intent.greeting_copy(), meta={"kind": "welcome"})
    return conv


def get_conversation(
    session: Session,
    public_id: str,
    *,
    user: Optional[User] = None,
    staff: bool = False,
) -> Optional[ShippingConversation]:
    conv = session.exec(
        select(ShippingConversation).where(ShippingConversation.public_id == public_id)
    ).first()
    if not conv:
        return None
    if staff:
        return conv
    if user and conv.user_id and conv.user_id != user.id:
        return None
    if user and conv.user_id is None:
        conv.user_id = user.id
        if not conv.seller_id:
            seller = _seller_for_user(session, user)
            if seller:
                conv.seller_id = seller.id
        session.add(conv)
        session.commit()
        session.refresh(conv)
    return conv


def messages_for(session: Session, conv: ShippingConversation) -> list[dict]:
    rows = session.exec(
        select(ShippingMessage)
        .where(ShippingMessage.conversation_id == conv.id)
        .order_by(ShippingMessage.created_at.asc())
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
    conv: ShippingConversation,
    role: str,
    body: str,
    *,
    meta: dict | None = None,
) -> ShippingMessage:
    msg = ShippingMessage(
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
    conv: ShippingConversation,
    role: str,
    body: str,
    *,
    meta: dict | None = None,
) -> ShippingMessage:
    return _add_msg(session, conv, role, body, meta=meta)


def _pack(conv: ShippingConversation, session: Session, reply: str, extra: dict) -> dict:
    return {
        "conversation_id": conv.public_id,
        "id": conv.public_id,
        "status": conv.status,
        "intent": conv.intent,
        "confidence": conv.confidence,
        "tone": conv.tone,
        "order_id": conv.order_id,
        "entities": conv.entities or {},
        "workflow": conv.workflow,
        "workflow_step": conv.workflow_step,
        "reply": reply,
        **extra,
    }


def _chips_for(intent_name: str) -> list[str]:
    base = [
        "Orders to ship",
        "Create a label",
        "Quote shipping rates",
        "How should I pack a slab?",
    ]
    extra = {
        "list_to_ship": ["Create a label for the oldest", "Quote rates for #"],
        "create_label": ["Track that shipment", "Orders to ship"],
        "quote_rates": ["Create a label with the recommended rate", "Cheapest option"],
        "track_shipment": ["Flag a shipping exception", "Orders to ship"],
    }.get(intent_name, [])
    return (extra + base)[:5]


def _resolve_order(session: Session, conv: ShippingConversation, intake, user: Optional[User]):
    order_id = intake.entities.get("order_id") or conv.order_id
    if not order_id:
        return None, "I need an order number — try “create a label for order #1042”."
    order = actions.get_seller_order(
        session, int(order_id),
        seller_id=conv.seller_id,
        user_id=user.id if user else None,
        staff=is_staff(user),
    )
    if not order:
        from ..models import Order
        cand = session.get(Order, int(order_id))
        if cand and (is_staff(user) or conv.seller_id is None or cand.seller_id == conv.seller_id):
            order = cand
    if not order:
        return None, f"I couldn't access order #{order_id}. Check the number or sign in as the seller."
    conv.order_id = order.id
    session.add(conv)
    session.commit()
    return order, None


def handle_message(
    session: Session,
    conv: ShippingConversation,
    text: str,
    *,
    user: Optional[User] = None,
) -> dict:
    text = (text or "").strip()
    if not text:
        return _pack(conv, session, "Tell me what you need — rates, labels, packing, or tracking.", {})

    _add_msg(session, conv, "user", text)
    knowledge.ensure_knowledge(session)

    intake = intent.classify(text, prior_entities=conv.entities or {})
    conv.intent = intake.intent
    conv.confidence = intake.confidence
    conv.tone = intake.tone
    conv.entities = intake.entities
    if intake.entities.get("order_id"):
        conv.order_id = intake.entities["order_id"]
    if intake.entities.get("address") and intake.intent in ("set_ship_from", "validate_address", "quote_rates"):
        ctx = dict(conv.context or {})
        if intake.intent == "set_ship_from":
            ctx["ship_from"] = intake.entities["address"]
        else:
            ctx["ship_to"] = intake.entities.get("address") or ctx.get("ship_to")
        conv.context = ctx
    conv.updated_at = utcnow()
    session.add(conv)
    session.commit()
    session.refresh(conv)

    if intake.clarifying_question and (
        intake.confidence < 0.7
        or intake.intent in {
            "create_label", "ship_order", "track_shipment", "quote_rates",
            "handle_exception", "set_ship_from", "validate_address",
        }
        and intake.clarifying_question
    ):
        # Only block when we truly lack required entities.
        needs_block = False
        if intake.intent in {"create_label", "ship_order", "quote_rates", "handle_exception"}:
            needs_block = not intake.entities.get("order_id")
        elif intake.intent == "track_shipment":
            needs_block = not (intake.entities.get("order_id") or intake.entities.get("tracking_number"))
        elif intake.intent in {"set_ship_from", "validate_address"}:
            needs_block = not intake.entities.get("address")
        if needs_block:
            reply = intake.clarifying_question
            _add_msg(session, conv, "assistant", reply, meta={"clarify": True})
            return _pack(conv, session, reply, {
                "intent": intake.intent,
                "confidence": intake.confidence,
                "chips": _chips_for(intake.intent),
                "status": "awaiting_user",
            })

    prefer = intake.entities.get("prefer") or "balanced"

    if intake.intent == "greeting":
        reply = intent.greeting_copy()
        _add_msg(session, conv, "assistant", reply)
        return _pack(conv, session, reply, {
            "intent": "greeting",
            "confidence": intake.confidence,
            "chips": _chips_for("greeting"),
        })

    if intake.intent == "list_to_ship":
        result = workflow.run_to_ship(
            session, conv, seller_id=conv.seller_id, confidence=intake.confidence,
        )
        items = result.get("to_ship") or []
        if not items:
            reply = "No paid orders waiting to ship. When sales come in, they'll show up here."
        else:
            lines = [f"• #{i['id']} — {i['title']} (${i['price']:.2f})" for i in items[:10]]
            reply = f"{len(items)} order(s) ready to ship:\n" + "\n".join(lines)
            reply += "\n\nSay “create a label for order #ID” and I'll handle postage + tracking."
        _add_msg(session, conv, "assistant", reply, meta={"workflow": result})
        return _pack(conv, session, reply, {
            "intent": intake.intent,
            "confidence": intake.confidence,
            "workflow": result,
            "chips": _chips_for(intake.intent),
        })

    if intake.intent == "set_ship_from":
        addr = intake.entities.get("address") or (conv.context or {}).get("ship_from")
        if not addr:
            reply = "Paste your ship-from like: 123 Main St, Austin TX 78701"
            _add_msg(session, conv, "assistant", reply)
            return _pack(conv, session, reply, {"intent": intake.intent, "chips": _chips_for(intake.intent)})
        if conv.seller_id:
            actions.upsert_ship_from(session, seller_id=conv.seller_id, address=addr, prefer=prefer)
        ctx = dict(conv.context or {})
        ctx["ship_from"] = addr
        conv.context = ctx
        session.add(conv)
        session.commit()
        reply = (
            f"Saved ship-from: {addr.get('street1')}, {addr.get('city')} "
            f"{addr.get('state')} {addr.get('zip')}. I'll use it for rate quotes and labels."
        )
        _add_msg(session, conv, "assistant", reply)
        return _pack(conv, session, reply, {"intent": intake.intent, "ship_from": addr})

    if intake.intent == "validate_address":
        addr = intake.entities.get("address") or (conv.context or {}).get("ship_to")
        from .. import shipping as ship
        result = ship.validate_address(addr or {})
        reply = result.get("message") or ("Looks good." if result.get("ok") else "Address needs a fix.")
        if result.get("address"):
            a = result["address"]
            reply += f"\n{a.get('street1')}, {a.get('city')} {a.get('state')} {a.get('zip')}"
        _add_msg(session, conv, "assistant", reply, meta={"validation": result})
        return _pack(conv, session, reply, {
            "intent": intake.intent,
            "validation": result,
            "chips": _chips_for(intake.intent),
        })

    if intake.intent in ("recommend_packaging", "insurance_advice"):
        order = None
        if intake.entities.get("order_id") or conv.order_id:
            order, err = _resolve_order(session, conv, intake, user)
            if err and intake.intent == "insurance_advice":
                pass
        is_graded = bool(intake.entities.get("is_graded"))
        value = order.price_cents if order else 0
        result = workflow.run_packaging(
            session, conv, order=order, is_graded=is_graded,
            value_cents=value, confidence=intake.confidence,
        )
        pack = result["packaging"]
        insure = result["insurance"]
        tips = "\n".join(f"• {t}" for t in pack.get("tips") or [])
        reply = (
            f"**{pack['label']}**\n"
            f"Parcel: {pack['parcel']['length']}×{pack['parcel']['width']}×"
            f"{pack['parcel']['height']} in, {pack['parcel']['weight']} "
            f"{pack['parcel']['mass_unit']}.\n"
            f"{insure['reason']}\n{tips}"
        )
        _add_msg(session, conv, "assistant", reply, meta={"workflow": result})
        return _pack(conv, session, reply, {
            "intent": intake.intent,
            "confidence": intake.confidence,
            "workflow": result,
            "chips": _chips_for(intake.intent),
        })

    if intake.intent == "shipping_policy":
        arts = knowledge.search(session, text, limit=3)
        if not arts:
            reply = "Ship paid orders within 3 business days and always add tracking."
        else:
            reply = "\n\n".join(f"**{a['title']}**\n{a['body']}" for a in arts)
        _add_msg(session, conv, "assistant", reply)
        return _pack(conv, session, reply, {
            "intent": intake.intent,
            "articles": arts,
            "chips": _chips_for(intake.intent),
        })

    # Intents that need an order (or tracking).
    if intake.intent == "track_shipment" and intake.entities.get("tracking_number") and not intake.entities.get("order_id"):
        result = workflow.run_track(
            session, conv,
            tracking_number=intake.entities["tracking_number"],
            confidence=intake.confidence,
        )
        tr = result["tracking"]
        reply = (
            f"Tracking **{tr.get('tracking_number')}**"
            + (f" via {tr.get('carrier')}" if tr.get("carrier") else "")
            + f" — status: **{tr.get('status')}**."
        )
        if tr.get("tracking_url"):
            reply += f"\nTrack: {tr['tracking_url']}"
        _add_msg(session, conv, "assistant", reply, meta={"workflow": result})
        return _pack(conv, session, reply, {
            "intent": intake.intent,
            "workflow": result,
            "chips": _chips_for(intake.intent),
        })

    order, err = _resolve_order(session, conv, intake, user)
    if err:
        # Soft fallback: packaging without order already handled.
        reply = err
        _add_msg(session, conv, "assistant", reply)
        return _pack(conv, session, reply, {
            "intent": intake.intent,
            "confidence": intake.confidence,
            "chips": _chips_for(intake.intent),
            "status": "awaiting_user",
        })

    if intake.intent == "quote_rates":
        result = workflow.run_quote(
            session, conv, order, prefer=prefer, confidence=intake.confidence,
        )
        q = result["quote"]
        rec = q.get("recommended") or {}
        pack = q.get("packaging") or {}
        reply = (
            f"Order #{order.id} — recommended **{rec.get('provider')} {rec.get('service')}** "
            f"at **${rec.get('amount')}** (~{rec.get('days')} day(s)). "
            f"{rec.get('reason')}\n"
            f"Pack as: {pack.get('label')}."
        )
        if q.get("insurance_cents"):
            reply += f"\nSuggested insurance: ${q['insurance_cents'] / 100:.2f}."
        if not q.get("shippo_live"):
            reply += "\n_(Demo rates — set SHIPPO_API_KEY for live postage.)_"
        reply += "\nSay “create a label” to buy postage and mark it shipped."
        _add_msg(session, conv, "assistant", reply, meta={"workflow": result})
        return _pack(conv, session, reply, {
            "intent": intake.intent,
            "confidence": intake.confidence,
            "workflow": result,
            "chips": ["Create a label for this order", "Cheapest rate", "Orders to ship"],
        })

    if intake.intent == "create_label":
        result = workflow.run_label(
            session, conv, order, prefer=prefer, confidence=intake.confidence,
        )
        if result["decision"] == "deny":
            reply = result.get("policy", {}).get("reason") or "Can't create a label for this order."
        elif result["decision"] == "escalate":
            reply = (
                "This looks high-risk / high-value — I queued it for human review before "
                "buying postage. Case " + conv.public_id + "."
            )
        else:
            label = result.get("label") or {}
            reply = (
                f"Label **{label.get('label_id')}** ready — "
                f"{label.get('carrier')} {label.get('service') or ''} "
                f"(${label.get('amount')}). Tracking **{label.get('tracking_number')}**."
            )
            if label.get("label_url"):
                reply += f"\nDownload: {label['label_url']}"
            if label.get("note"):
                reply += f"\n_{label['note']}_"
            if "mark_shipped" in result.get("actions_taken", []):
                reply += "\nOrder marked **shipped** and the buyer was notified."
        _add_msg(session, conv, "assistant", reply, meta={"workflow": result})
        return _pack(conv, session, reply, {
            "intent": intake.intent,
            "confidence": intake.confidence,
            "workflow": result,
            "chips": _chips_for(intake.intent),
        })

    if intake.intent == "ship_order":
        tracking = intake.entities.get("tracking_number")
        if not tracking and (conv.context or {}).get("last_label"):
            tracking = conv.context["last_label"].get("tracking_number")
        if not tracking:
            reply = "Paste the tracking number and I'll mark the order shipped."
            _add_msg(session, conv, "assistant", reply)
            return _pack(conv, session, reply, {"intent": intake.intent, "status": "awaiting_user"})
        result = workflow.run_ship(
            session, conv, order,
            tracking_number=tracking,
            confidence=intake.confidence,
        )
        if result["decision"] != "approve":
            reply = result.get("policy", {}).get("reason") or "Couldn't mark shipped."
        else:
            o = result.get("order") or {}
            reply = (
                f"Order #{o.get('id')} marked **shipped** via {o.get('carrier') or 'carrier'}. "
                f"Tracking {o.get('tracking_number')}."
            )
            if o.get("tracking_url"):
                reply += f"\n{o['tracking_url']}"
        _add_msg(session, conv, "assistant", reply, meta={"workflow": result})
        return _pack(conv, session, reply, {
            "intent": intake.intent,
            "workflow": result,
            "chips": _chips_for(intake.intent),
        })

    if intake.intent == "track_shipment":
        result = workflow.run_track(
            session, conv, order=order, confidence=intake.confidence,
        )
        tr = result["tracking"]
        o = result.get("order") or {}
        if not tr.get("tracking_number"):
            reply = f"Order #{order.id} is **{o.get('status')}** — no tracking yet. Want me to create a label?"
        else:
            reply = (
                f"Order #{order.id} — **{tr.get('status')}** "
                f"({tr.get('carrier') or 'carrier'} {tr.get('tracking_number')})."
            )
            if tr.get("tracking_url"):
                reply += f"\n{tr['tracking_url']}"
        _add_msg(session, conv, "assistant", reply, meta={"workflow": result})
        return _pack(conv, session, reply, {
            "intent": intake.intent,
            "workflow": result,
            "chips": _chips_for(intake.intent),
        })

    if intake.intent == "handle_exception":
        result = workflow.run_exception(
            session, conv, order, reason=text, confidence=intake.confidence,
        )
        if result["decision"] == "escalate":
            reply = (
                f"Flagged order #{order.id} for shipping review (possible delay/loss). "
                f"Case {conv.public_id}. Tracking status: "
                f"**{(result.get('tracking') or {}).get('status', 'unknown')}**."
            )
        else:
            tr = result.get("tracking") or {}
            reply = (
                f"Order #{order.id} tracking shows **{tr.get('status', 'unknown')}**. "
                "If there's still no movement in a few days, ask me to escalate."
            )
            if tr.get("tracking_url"):
                reply += f"\n{tr['tracking_url']}"
        _add_msg(session, conv, "assistant", reply, meta={"workflow": result})
        return _pack(conv, session, reply, {
            "intent": intake.intent,
            "workflow": result,
            "chips": _chips_for(intake.intent),
        })

    # Fallback — search KB or offer menu.
    arts = knowledge.search(session, text, limit=2)
    if arts:
        reply = "Here's what I know:\n\n" + "\n\n".join(
            f"**{a['title']}**\n{a['body']}" for a in arts
        )
    else:
        reply = (
            "I can quote rates, recommend packaging, create labels, mark shipped, "
            "track packages, or list orders waiting to ship. Try “orders to ship”."
        )
    _add_msg(session, conv, "assistant", reply)
    return _pack(conv, session, reply, {
        "intent": intake.intent or "other",
        "confidence": intake.confidence,
        "chips": _chips_for("other"),
    })

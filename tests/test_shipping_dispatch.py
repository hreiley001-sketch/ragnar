"""Tests for Dispatch — AI shipping agent."""
from __future__ import annotations

import os
import uuid

os.environ["DATABASE_URL"] = "sqlite:///./test_shipping_dispatch.db"
os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("SHIPPO_API_KEY", None)

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

from app.database import engine, init_db
from app.main import app
from app.models import Order, OrderStatus, Seller, User
from app.shipping import detect_carrier, recommend_packaging, recommend_rate
from app.shipping_agent import intent, knowledge, policy


def setup_module(_mod=None):
    SQLModel.metadata.drop_all(engine)
    init_db()


def _session():
    return Session(engine)


def _uid():
    return uuid.uuid4().hex[:8]


def _seed_order(*, price_cents=12000, status=OrderStatus.paid.value, graded=False):
    tag = _uid()
    with _session() as s:
        user = User(email=f"seller-{tag}@example.com", name="Seller", email_verified=True)
        s.add(user)
        s.commit()
        s.refresh(user)
        seller = Seller(
            handle=f"ship{tag}", display_name="Ship Shop", email=user.email,
        )
        s.add(seller)
        s.commit()
        s.refresh(seller)
        order = Order(
            seller_id=seller.id,
            buyer_user_id=user.id,
            buyer_name="Buyer",
            buyer_email=f"buyer-{tag}@example.com",
            title="PSA 10 Charizard" if graded else "Raw Charizard",
            price_cents=price_cents,
            shipping_cents=500,
            status=status,
            source="manual",
        )
        s.add(order)
        s.commit()
        s.refresh(order)
        return user.id, seller.id, order.id


def test_detect_carrier_ups():
    assert detect_carrier("1Z999AA10123456784") == "UPS"


def test_detect_carrier_usps():
    assert detect_carrier("9400111899223344556677") == "USPS"


def test_recommend_packaging_slab():
    pack = recommend_packaging(is_graded=True, quantity=1, value_cents=15_000)
    assert pack["package_key"] == "slab_single"
    assert pack["recommended_insurance_cents"] >= 10_000


def test_recommend_rate_balanced():
    rates = [
        {"provider": "USPS", "service": "Ground", "amount": "4.00", "days": 6},
        {"provider": "USPS", "service": "Priority", "amount": "8.00", "days": 2},
        {"provider": "UPS", "service": "Next Day", "amount": "40.00", "days": 1},
    ]
    best = recommend_rate(rates, prefer="balanced")
    assert best["service"] in ("Priority", "Ground")


def test_intent_create_label():
    r = intent.classify("Please create a shipping label for order #77")
    assert r.intent == "create_label"
    assert r.entities.get("order_id") == 77


def test_intent_to_ship():
    r = intent.classify("What orders need shipping?")
    assert r.intent == "list_to_ship"


def test_policy_label_high_value():
    order = Order(
        title="Grail", price_cents=60_000, shipping_cents=0,
        status=OrderStatus.paid.value,
    )
    d = policy.evaluate_label(order=order)
    assert d.decision == "approve"
    assert d.risk == "high"
    assert "require_signature" in d.actions


def test_api_status_and_chat_packaging():
    client = TestClient(app)
    st = client.get("/api/shipping/status")
    assert st.status_code == 200
    assert st.json()["agent"] == "dispatch"
    assert "create_label" in st.json()["capabilities"]

    start = client.post("/api/shipping/conversations", json={"channel": "web"})
    assert start.status_code == 200
    conv_id = start.json()["id"]
    assert conv_id.startswith("shp_")

    chat = client.post("/api/shipping/chat", json={
        "conversation_id": conv_id,
        "message": "How should I pack a graded slab?",
    })
    assert chat.status_code == 200
    data = chat.json()
    assert data["intent"] == "recommend_packaging"
    assert "slab" in (data["reply"] or "").lower() or "pack" in (data["reply"] or "").lower()


def test_api_quote_and_label_flow():
    _, _, order_id = _seed_order(price_cents=8500)
    client = TestClient(app)
    start = client.post("/api/shipping/conversations", json={"channel": "web"})
    conv_id = start.json()["id"]

    quote = client.post("/api/shipping/chat", json={
        "conversation_id": conv_id,
        "message": f"Quote shipping rates for order #{order_id}",
    })
    assert quote.status_code == 200
    qdata = quote.json()
    assert qdata["intent"] == "quote_rates"
    assert qdata.get("workflow", {}).get("quote", {}).get("recommended")

    label = client.post("/api/shipping/chat", json={
        "conversation_id": conv_id,
        "message": f"Create a label for order #{order_id}",
    })
    assert label.status_code == 200
    ldata = label.json()
    assert ldata["intent"] == "create_label"
    wf = ldata.get("workflow") or {}
    assert wf.get("decision") in ("approve", "escalate")
    if wf.get("decision") == "approve":
        assert wf.get("label", {}).get("tracking_number")
        assert "mark_shipped" in (wf.get("actions_taken") or [])


def test_api_to_ship_lists_paid():
    _, seller_id, order_id = _seed_order()
    client = TestClient(app)
    start = client.post("/api/shipping/conversations", json={"channel": "web"})
    conv_id = start.json()["id"]
    # Attach seller on conversation via DB so queue filters.
    with _session() as s:
        from app.models import ShippingConversation
        from sqlmodel import select
        conv = s.exec(
            select(ShippingConversation).where(ShippingConversation.public_id == conv_id)
        ).first()
        conv.seller_id = seller_id
        s.add(conv)
        s.commit()

    resp = client.post("/api/shipping/chat", json={
        "conversation_id": conv_id,
        "message": "Orders to ship",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "list_to_ship"
    ids = [i["id"] for i in (data.get("workflow") or {}).get("to_ship") or []]
    assert order_id in ids


def test_knowledge_seed():
    with _session() as s:
        n = knowledge.ensure_knowledge(s)
        assert n >= 0
        items = knowledge.search(s, "pack slab", limit=3)
        assert items

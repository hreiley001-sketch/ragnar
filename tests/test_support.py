"""Tests for the AI Support OS — intake, policy, workflows, API."""
from __future__ import annotations

import os
import uuid

# Isolate test DB before app imports bind the engine.
os.environ["DATABASE_URL"] = "sqlite:///./test_support.db"
os.environ.pop("OPENAI_API_KEY", None)

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

from app.database import engine, init_db
from app.main import app
from app.models import Order, OrderStatus, Seller, User, utcnow
from app.support import brain, intent, knowledge, policy
from app.support.governance import autonomy_band


def setup_module(_mod=None):
    SQLModel.metadata.drop_all(engine)
    init_db()


def _session():
    return Session(engine)


def _uid():
    return uuid.uuid4().hex[:8]


def _seed_buyer_order(*, price_cents=5000, status=OrderStatus.paid.value, title="PSA 10 Charizard"):
    tag = _uid()
    with _session() as s:
        user = User(email=f"buyer-{tag}@example.com", name="Buyer", email_verified=True)
        s.add(user)
        s.commit()
        s.refresh(user)
        seller = Seller(
            handle=f"shop{tag}", display_name="Test Shop", email=f"seller-{tag}@example.com",
        )
        s.add(seller)
        s.commit()
        s.refresh(seller)
        order = Order(
            seller_id=seller.id,
            buyer_user_id=user.id,
            buyer_name="Buyer",
            buyer_email=user.email,
            title=title,
            price_cents=price_cents,
            shipping_cents=500,
            status=status,
            source="manual",
        )
        s.add(order)
        s.commit()
        s.refresh(order)
        return user.id, order.id


def test_intent_refund_and_entities():
    r = intent.classify("I need a refund on order #42 — the card never arrived")
    assert r.intent in ("process_refund", "report_item_not_received")
    assert r.entities.get("order_id") == 42
    assert r.confidence >= 0.7


def test_intent_tracking():
    r = intent.classify("Where is my package? tracking for order 99")
    assert r.intent == "track_order"
    assert r.entities.get("order_id") == 99


def test_intent_security_escalates_tone():
    r = intent.classify("I think my account was hacked and there's fraud")
    assert r.intent == "account_security_issue"
    assert r.tone == "high_risk"


def test_governance_bands():
    assert autonomy_band(0.95, "low") == "act"
    assert autonomy_band(0.8, "low") == "flag_review"
    assert autonomy_band(0.5, "low") == "escalate"
    assert autonomy_band(0.99, "high") == "escalate"


def test_policy_refund_pre_ship():
    with _session() as s:
        knowledge.ensure_knowledge(s)
        order = Order(
            title="Card", price_cents=4000, shipping_cents=0,
            status=OrderStatus.paid.value, created_at=utcnow(),
        )
        s.add(order)
        s.commit()
        s.refresh(order)
        d = policy.evaluate_refund(s, order=order, user_id=None, reason="changed mind")
        assert d.decision == "approve"
        assert "issue_refund" in d.actions


def test_policy_high_value_escalates():
    with _session() as s:
        order = Order(
            title="Grail", price_cents=80_000, shipping_cents=0,
            status=OrderStatus.delivered.value, created_at=utcnow(),
        )
        s.add(order)
        s.commit()
        s.refresh(order)
        d = policy.evaluate_refund(s, order=order, user_id=None, reason="not as described")
        assert d.decision == "escalate"
        assert d.queue == "high_value"


def test_knowledge_search():
    with _session() as s:
        knowledge.ensure_knowledge(s)
        hits = knowledge.search(s, "refund window buyer protection")
        assert hits
        assert any("refund" in h["slug"] or "buyer" in h["slug"] for h in hits)


def test_api_start_and_chat_fees():
    client = TestClient(app)
    start = client.post("/api/support/conversations", json={"channel": "web"})
    assert start.status_code == 200
    data = start.json()
    assert data["id"].startswith("sup_")
    assert data["messages"]

    chat = client.post("/api/support/chat", json={
        "conversation_id": data["id"],
        "message": "What are your seller fees?",
    })
    assert chat.status_code == 200
    body = chat.json()
    assert body["reply"]
    assert "fee" in body["reply"].lower() or "5%" in body["reply"] or "Founding" in body["reply"]


def test_ensure_knowledge_recovers_missing_tables(tmp_path, monkeypatch):
    """Old DBs without Support tables should self-heal via ensure_knowledge."""
    import app.database as db
    from sqlmodel import Session as S
    from app.support import knowledge as kb

    fresh = tmp_path / "heal.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{fresh}")
    # Rebuild engine against empty file (no tables).
    from sqlmodel import create_engine as ce
    new_engine = ce(f"sqlite:///{fresh}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(db, "engine", new_engine)
    # create_all not called yet — ensure_knowledge must recover.
    with S(new_engine) as s:
        kb.ensure_knowledge(s)
        hits = kb.search(s, "refund")
        assert hits


def test_api_track_requires_auth_for_privacy():
    _user_id, order_id = _seed_buyer_order(status=OrderStatus.shipped.value)
    client = TestClient(app)
    start = client.post("/api/support/conversations").json()
    track = client.post("/api/support/chat", json={
        "conversation_id": start["id"],
        "message": f"Track order #{order_id}",
    }).json()
    assert (
        "sign in" in track["reply"].lower()
        or "account" in track["reply"].lower()
        or "couldn't" in track["reply"].lower()
    )


def test_brain_track_and_refund():
    user_id, order_id = _seed_buyer_order(status=OrderStatus.shipped.value)
    with _session() as s:
        user = s.get(User, user_id)
        conv = brain.start_conversation(s, user=user)
        result = brain.handle_message(s, conv, f"Where is order #{order_id}?", user=user)
        assert result["intent"] == "track_order"
        assert result.get("workflow", {}).get("order", {}).get("id") == order_id

    with _session() as s:
        user = s.get(User, user_id)
        conv = brain.start_conversation(s, user=user)
        result2 = brain.handle_message(
            s, conv, f"Refund order #{order_id} — item not received", user=user,
        )
        wf = result2.get("workflow") or {}
        assert wf.get("decision") == "approve"
        assert any("refund" in a for a in wf.get("actions_taken", []))


def test_api_knowledge_list():
    client = TestClient(app)
    r = client.get("/api/support/knowledge")
    assert r.status_code == 200
    assert len(r.json()["items"]) >= 5


def test_cancel_before_ship():
    user_id, order_id = _seed_buyer_order(status=OrderStatus.paid.value, price_cents=3000)
    with _session() as s:
        user = s.get(User, user_id)
        conv = brain.start_conversation(s, user=user)
        result = brain.handle_message(s, conv, f"Please cancel order #{order_id}", user=user)
        assert result.get("workflow", {}).get("decision") == "approve"
        order = s.get(Order, order_id)
        s.refresh(order)
        assert order.status == OrderStatus.cancelled.value

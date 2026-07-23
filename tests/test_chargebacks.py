"""Stripe chargeback desk — dispute webhook → Chargeback + trust score."""
from __future__ import annotations

import os
import uuid

os.environ["DATABASE_URL"] = "sqlite:///./test_chargebacks.db"
os.environ["ADMIN_TOKEN"] = "test-admin-token-cb"
os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("STRIPE_SECRET_KEY", None)

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, select

from app.auth import hash_password
from app.chargebacks import apply_dispute_event
from app.config import settings
from app.database import engine, init_db
from app.main import app
from app.models import (
    Category,
    Chargeback,
    Condition,
    Dispute,
    Listing,
    ListingStatus,
    Order,
    OrderStatus,
    Seller,
    TrustEvent,
    User,
    UserRole,
)

ADMIN = {"X-Admin-Token": "test-admin-token-cb"}


def setup_module(_mod=None):
    SQLModel.metadata.drop_all(engine)
    init_db()
    settings.admin_token = "test-admin-token-cb"


def setup_function(_fn=None):
    settings.admin_token = "test-admin-token-cb"


def _session():
    return Session(engine)


def _uid():
    return uuid.uuid4().hex[:8]


def _seed_order():
    tag = _uid()
    pi = f"pi_{tag}"
    with _session() as s:
        seller = Seller(
            handle=f"s{tag}",
            display_name="Seller",
            email=f"s{tag}@ex.com",
            stripe_charges_enabled=True,
            fraud_score=5,
        )
        s.add(seller)
        s.commit()
        s.refresh(seller)
        listing = Listing(
            title="Card",
            category=list(Category)[0].value,
            is_graded=False,
            condition=list(Condition)[0].value,
            price_cents=5000,
            quantity=0,
            seller_id=seller.id,
            seller_name=seller.display_name,
            status=ListingStatus.sold.value,
        )
        s.add(listing)
        s.commit()
        s.refresh(listing)
        order = Order(
            listing_id=listing.id,
            seller_id=seller.id,
            title=listing.title,
            price_cents=5000,
            status=OrderStatus.paid.value,
            stripe_session_id=f"cs_{tag}",
            stripe_payment_intent_id=pi,
            source="stripe",
        )
        s.add(order)
        s.commit()
        s.refresh(order)
        return order.id, seller.id, seller.handle, pi


def test_charge_dispute_created_opens_chargeback_and_bumps_score():
    order_id, seller_id, handle, pi = _seed_order()
    with _session() as s:
        result = apply_dispute_event(
            s,
            {
                "id": f"dp_{_uid()}",
                "status": "needs_response",
                "reason": "fraudulent",
                "amount": 5000,
                "currency": "usd",
                "payment_intent": pi,
                "charge": f"ch_{_uid()}",
                "metadata": {},
            },
            "charge.dispute.created",
        )
        assert result["ok"] is True
        assert result["created"] is True
        assert result["order_id"] == order_id

        cb = s.exec(select(Chargeback).where(Chargeback.order_id == order_id)).one()
        assert cb.status == "needs_response"
        assert cb.seller_id == seller_id

        order = s.get(Order, order_id)
        assert order.status == OrderStatus.disputed.value
        disputes = s.exec(select(Dispute).where(Dispute.order_id == order_id)).all()
        assert len(disputes) == 1

        seller = s.get(Seller, seller_id)
        assert seller.fraud_score >= 20
        events = s.exec(
            select(TrustEvent).where(TrustEvent.seller_id == seller_id)
        ).all()
        assert any(e.event_type == "chargeback_opened" for e in events)


def test_charge_dispute_lost_resolves_refund():
    order_id, seller_id, _, pi = _seed_order()
    dp = f"dp_{_uid()}"
    with _session() as s:
        apply_dispute_event(
            s,
            {
                "id": dp,
                "status": "needs_response",
                "reason": "product_not_received",
                "amount": 5000,
                "currency": "usd",
                "payment_intent": pi,
            },
            "charge.dispute.created",
        )
        apply_dispute_event(
            s,
            {
                "id": dp,
                "status": "lost",
                "reason": "product_not_received",
                "amount": 5000,
                "currency": "usd",
                "payment_intent": pi,
            },
            "charge.dispute.closed",
        )
        order = s.get(Order, order_id)
        assert order.status == OrderStatus.refunded.value
        dispute = s.exec(select(Dispute).where(Dispute.order_id == order_id)).one()
        assert dispute.status == "resolved_refund"
        cb = s.exec(select(Chargeback).where(Chargeback.stripe_dispute_id == dp)).one()
        assert cb.status == "lost"
        assert cb.closed_at is not None


def test_admin_lists_chargebacks():
    _, _, _, pi = _seed_order()
    with _session() as s:
        apply_dispute_event(
            s,
            {
                "id": f"dp_{_uid()}",
                "status": "under_review",
                "reason": "general",
                "amount": 1200,
                "currency": "usd",
                "payment_intent": pi,
            },
            "charge.dispute.updated",
        )
    client = TestClient(app)
    r = client.get("/api/admin/trust/chargebacks", headers=ADMIN)
    assert r.status_code == 200, r.text
    assert r.json()["count"] >= 1

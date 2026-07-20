"""Phase 3 — real Stripe refunds; no fake success paths."""
from __future__ import annotations

import os
import uuid
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///./test_refunds.db"
os.environ.pop("OPENAI_API_KEY", None)

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, select

from app.config import settings
from app.database import engine, init_db
from app.main import app
from app.models import (
    Dispute,
    Order,
    OrderStatus,
    Seller,
    SupportRefund,
    User,
)
from app.support import actions

client = TestClient(app)
ADMIN_HEADERS = {"X-Admin-Token": "test-admin-token"}


def setup_module(_mod=None):
    SQLModel.metadata.drop_all(engine)
    init_db()
    settings.admin_token = "test-admin-token"


def _session():
    return Session(engine)


def _uid():
    return uuid.uuid4().hex[:8]


def _seed_order(*, stripe_session_id: str | None = None, status: str = OrderStatus.paid.value):
    tag = _uid()
    with _session() as s:
        user = User(email=f"b-{tag}@example.com", name="Buyer", email_verified=True)
        s.add(user)
        s.commit()
        s.refresh(user)
        seller = Seller(handle=f"shop{tag}", display_name="Shop", email=f"s-{tag}@example.com")
        s.add(seller)
        s.commit()
        s.refresh(seller)
        order = Order(
            seller_id=seller.id,
            buyer_user_id=user.id,
            buyer_name="Buyer",
            buyer_email=user.email,
            title="Refund Card",
            price_cents=5000,
            shipping_cents=500,
            status=status,
            stripe_session_id=stripe_session_id,
            source="stripe" if stripe_session_id else "manual",
        )
        s.add(order)
        s.commit()
        s.refresh(order)
        return order.id, user.id


def test_manual_order_refund_is_ledger_cancel_not_stripe():
    order_id, _ = _seed_order(stripe_session_id=None)
    with _session() as s:
        order = s.get(Order, order_id)
        result = actions.issue_refund(
            s, order, amount_cents=5500, reason="changed mind", issued_by="test",
        )
        assert result["ok"] is True
        assert result["status"] == "ledger_cancelled"
        assert result["stripe_refund_id"] is None
        order = s.get(Order, order_id)
        assert order.status == OrderStatus.cancelled.value
        row = s.exec(select(SupportRefund).where(SupportRefund.order_id == order_id)).first()
        assert row is not None
        assert row.status == "ledger_cancelled"


def test_stripe_order_success_marks_refunded():
    order_id, _ = _seed_order(stripe_session_id="cs_test_ok")
    with _session() as s:
        order = s.get(Order, order_id)
        with patch("app.support.payments_bridge.try_refund") as mock_rf:
            mock_rf.return_value = {
                "ok": True, "refund_id": "re_123", "status": "succeeded", "amount_cents": 5500,
            }
            result = actions.issue_refund(
                s, order, amount_cents=5500, reason="nad", issued_by="test",
            )
        assert result["ok"] is True
        assert result["status"] == "stripe_refunded"
        assert result["stripe_refund_id"] == "re_123"
        order = s.get(Order, order_id)
        assert order.status == OrderStatus.refunded.value
        assert order.stripe_refund_id == "re_123"
        assert order.refunded_cents == 5500


def test_stripe_order_failure_does_not_mutate_order():
    order_id, _ = _seed_order(stripe_session_id="cs_test_fail")
    with _session() as s:
        order = s.get(Order, order_id)
        with patch("app.support.payments_bridge.try_refund") as mock_rf:
            mock_rf.return_value = {"ok": False, "reason": "card_declined_sim"}
            result = actions.issue_refund(
                s, order, amount_cents=5500, reason="nad", issued_by="test",
            )
        assert result["ok"] is False
        order = s.get(Order, order_id)
        assert order.status == OrderStatus.paid.value
        assert (order.refunded_cents or 0) == 0
        assert s.exec(select(SupportRefund).where(SupportRefund.order_id == order_id)).first() is None


def test_admin_dispute_refund_failure_keeps_dispute_open():
    order_id, user_id = _seed_order(stripe_session_id="cs_dispute_fail", status=OrderStatus.disputed.value)
    with _session() as s:
        d = Dispute(order_id=order_id, opened_by_user_id=user_id, reason="Never arrived")
        s.add(d)
        s.commit()
        s.refresh(d)
        dispute_id = d.id

    with patch("app.support.payments_bridge.try_refund") as mock_rf:
        mock_rf.return_value = {"ok": False, "reason": "stripe down"}
        r = client.post(
            f"/api/admin/disputes/{dispute_id}/resolve",
            json={"status": "resolved_refund", "resolution": "Full refund"},
            headers=ADMIN_HEADERS,
        )
    assert r.status_code == 502, r.text
    with _session() as s:
        d = s.get(Dispute, dispute_id)
        assert d.status == "open"
        order = s.get(Order, order_id)
        assert order.status == OrderStatus.disputed.value


def test_admin_dispute_manual_refund_resolves():
    order_id, user_id = _seed_order(stripe_session_id=None, status=OrderStatus.disputed.value)
    with _session() as s:
        d = Dispute(order_id=order_id, opened_by_user_id=user_id, reason="Changed mind")
        s.add(d)
        s.commit()
        s.refresh(d)
        dispute_id = d.id

    r = client.post(
        f"/api/admin/disputes/{dispute_id}/resolve",
        json={"status": "resolved_refund", "resolution": "Cancel offline sale"},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "resolved_refund"
    assert body["refund"]["status"] == "ledger_cancelled"
    with _session() as s:
        order = s.get(Order, order_id)
        assert order.status == OrderStatus.cancelled.value

"""Phase 2 — webhook idempotency, duplicate orders, inventory holds."""
from __future__ import annotations

import os
import uuid
from datetime import timedelta

os.environ["DATABASE_URL"] = "sqlite:///./test_payments_idempotency.db"
os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("STRIPE_SECRET_KEY", None)

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, select

from app.auth import create_session, hash_password
from app.config import settings
from app.database import engine, init_db
from app.inventory import available_units, create_hold, held_units, release_expired_holds
from app.main import app
from app.models import (
    Category,
    Condition,
    InventoryHold,
    Listing,
    ListingStatus,
    Order,
    ProcessedStripeEvent,
    Seller,
    User,
    UserRole,
    utcnow,
)
from app.routers import payments as payments_router
from app.services import record_sale

COOKIE = settings.session_cookie


def setup_module(_mod=None):
    SQLModel.metadata.drop_all(engine)
    init_db()


def _session():
    return Session(engine)


def _uid():
    return uuid.uuid4().hex[:8]


def _seed_listing(quantity: int = 1):
    tag = _uid()
    with _session() as s:
        seller = Seller(handle=f"s{tag}", display_name="Seller", email=f"s{tag}@ex.com")
        s.add(seller)
        s.commit()
        s.refresh(seller)
        listing = Listing(
            title="Stock Card",
            category=list(Category)[0].value,
            is_graded=False,
            condition=list(Condition)[0].value,
            price_cents=1000,
            quantity=quantity,
            seller_id=seller.id,
            seller_name=seller.display_name,
            status=ListingStatus.active.value,
        )
        s.add(listing)
        s.commit()
        s.refresh(listing)
        return listing.id, seller.id


def test_available_units_respects_holds():
    listing_id, _ = _seed_listing(quantity=2)
    with _session() as s:
        listing = s.get(Listing, listing_id)
        assert available_units(s, listing) == 2
        create_hold(s, listing, stripe_session_id=f"cs_{_uid()}", buyer_user_id=None)
        listing = s.get(Listing, listing_id)
        assert held_units(s, listing_id) == 1
        assert available_units(s, listing) == 1


def test_hold_blocks_oversell():
    listing_id, _ = _seed_listing(quantity=1)
    with _session() as s:
        listing = s.get(Listing, listing_id)
        create_hold(s, listing, stripe_session_id=f"cs_a_{_uid()}")
        listing = s.get(Listing, listing_id)
        assert available_units(s, listing) == 0
        try:
            create_hold(s, listing, stripe_session_id=f"cs_b_{_uid()}")
            assert False, "expected InventoryError"
        except Exception as exc:
            assert "sold out" in str(exc).lower() or "reserved" in str(exc).lower()


def test_expired_holds_release_capacity():
    listing_id, _ = _seed_listing(quantity=1)
    with _session() as s:
        listing = s.get(Listing, listing_id)
        hold = create_hold(s, listing, stripe_session_id=f"cs_exp_{_uid()}")
        hold.expires_at = utcnow() - timedelta(minutes=1)
        s.add(hold)
        s.commit()
        listing = s.get(Listing, listing_id)
        assert available_units(s, listing) == 1
        assert release_expired_holds(s, listing_id) >= 0


def test_record_sale_decrements_quantity():
    listing_id, _ = _seed_listing(quantity=2)
    with _session() as s:
        listing = s.get(Listing, listing_id)
        record_sale(s, listing, 1000, source="test")
        s.commit()
        listing = s.get(Listing, listing_id)
        assert listing.quantity == 1
        assert listing.status == ListingStatus.active.value
        record_sale(s, listing, 1000, source="test")
        s.commit()
        listing = s.get(Listing, listing_id)
        assert listing.quantity == 0
        assert listing.status == ListingStatus.sold.value


def test_webhook_handler_idempotent_on_session():
    listing_id, seller_id = _seed_listing(quantity=1)
    session_id = f"cs_dup_{_uid()}"
    with _session() as s:
        listing = s.get(Listing, listing_id)
        create_hold(s, listing, stripe_session_id=session_id)
        obj = {
            "id": session_id,
            "amount_total": 1000,
            "metadata": {"listing_id": str(listing_id)},
            "customer_details": {"email": "buyer@example.com", "name": "Buyer"},
        }
        payments_router._handle_checkout_completed(s, obj)
        payments_router._handle_checkout_completed(s, obj)
        orders = s.exec(select(Order).where(Order.stripe_session_id == session_id)).all()
        assert len(orders) == 1
        listing = s.get(Listing, listing_id)
        assert listing.status == ListingStatus.sold.value


def test_processed_event_marker():
    eid = f"evt_{_uid()}"
    with _session() as s:
        assert not payments_router._already_processed(s, eid)
        payments_router._mark_processed(s, eid, "checkout.session.completed")
        assert payments_router._already_processed(s, eid)
        row = s.get(ProcessedStripeEvent, eid)
        assert row is not None
        assert row.event_type == "checkout.session.completed"


def test_checkout_endpoint_requires_auth_still():
    client = TestClient(app)
    listing_id, _ = _seed_listing(quantity=1)
    r = client.post(f"/api/payments/checkout/{listing_id}", json={})
    assert r.status_code == 401

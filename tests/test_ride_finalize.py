"""Live ride finalize must not invent paid sales."""
from __future__ import annotations

import os
import uuid

os.environ["DATABASE_URL"] = "sqlite:///./test_ride_finalize.db"
os.environ.pop("OPENAI_API_KEY", None)

from sqlmodel import Session, SQLModel, select

from app.database import engine, init_db
from app.models import (
    Category,
    Condition,
    Listing,
    ListingStatus,
    Order,
    OrderStatus,
    Ride,
    RideEvent,
    RideStatus,
    Seller,
)
from app.rides_engine import _finalize


def setup_module(_mod=None):
    SQLModel.metadata.drop_all(engine)
    init_db()


def _session():
    return Session(engine)


def _uid():
    return uuid.uuid4().hex[:8]


def test_finalize_does_not_mark_listing_sold_or_claim_payment():
    tag = _uid()
    with _session() as s:
        seller = Seller(handle=f"r{tag}", display_name="Rider", email=f"r{tag}@ex.com")
        s.add(seller)
        s.commit()
        s.refresh(seller)
        listing = Listing(
            title="Ride Card",
            category=list(Category)[0].value,
            is_graded=False,
            condition=list(Condition)[0].value,
            price_cents=10000,
            quantity=1,
            seller_id=seller.id,
            seller_name=seller.display_name,
            status=ListingStatus.active.value,
        )
        s.add(listing)
        s.commit()
        s.refresh(listing)
        ride = Ride(
            title="Test Ride",
            seller_id=seller.id,
            listing_id=listing.id,
            status=RideStatus.cooldown.value,
            current_phase="cooldown",
            phase_index=0,
            current_bidder="alice",
            current_bid_cents=5000,
            reserve_cents=1000,
        )
        s.add(ride)
        s.commit()
        s.refresh(ride)
        ride_id, listing_id = ride.id, listing.id

        _finalize(s, ride)

        listing = s.get(Listing, listing_id)
        assert listing.status == ListingStatus.active.value
        assert listing.quantity == 1

        ride = s.get(Ride, ride_id)
        assert ride.status == RideStatus.archived.value
        assert ride.winner == "alice"

        events = s.exec(select(RideEvent).where(RideEvent.ride_id == ride_id)).all()
        types = [e.type for e in events]
        assert "payment_captured" not in types
        assert "payment_due" in types
        assert "ride_complete" in types

        orders = s.exec(select(Order).where(Order.listing_id == listing_id)).all()
        assert len(orders) == 1
        assert orders[0].status == OrderStatus.pending.value
        assert orders[0].source == "ride"

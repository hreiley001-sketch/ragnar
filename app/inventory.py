"""Inventory availability and checkout holds (anti-oversell)."""
from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session, select

from .models import InventoryHold, Listing, ListingStatus, utcnow

HOLD_TTL_MINUTES = 35  # Stripe Checkout sessions typically expire ~30m


class InventoryError(Exception):
    """Raised when a listing cannot be reserved."""


def _active_hold_filters(listing_id: int, now=None):
    now = now or utcnow()
    return [
        InventoryHold.listing_id == listing_id,
        InventoryHold.released == False,  # noqa: E712
        InventoryHold.converted == False,  # noqa: E712
        InventoryHold.expires_at > now,
    ]


def release_expired_holds(session: Session, listing_id: int | None = None) -> int:
    """Mark expired holds as released so capacity returns. Returns count released."""
    now = utcnow()
    stmt = select(InventoryHold).where(
        InventoryHold.released == False,  # noqa: E712
        InventoryHold.converted == False,  # noqa: E712
        InventoryHold.expires_at <= now,
    )
    if listing_id is not None:
        stmt = stmt.where(InventoryHold.listing_id == listing_id)
    rows = list(session.exec(stmt).all())
    for h in rows:
        h.released = True
        session.add(h)
    if rows:
        session.commit()
    return len(rows)


def held_units(session: Session, listing_id: int) -> int:
    release_expired_holds(session, listing_id)
    rows = session.exec(
        select(InventoryHold).where(*_active_hold_filters(listing_id))
    ).all()
    return sum(max(1, h.quantity or 1) for h in rows)


def available_units(session: Session, listing: Listing) -> int:
    if listing.status != ListingStatus.active.value:
        return 0
    qty = max(0, int(listing.quantity or 0))
    return max(0, qty - held_units(session, listing.id))


def assert_purchasable(session: Session, listing: Listing) -> None:
    if listing.status != ListingStatus.active.value:
        raise InventoryError("Listing is not active")
    if available_units(session, listing) < 1:
        raise InventoryError("This listing is sold out or reserved by another checkout")


def create_hold(
    session: Session,
    listing: Listing,
    *,
    stripe_session_id: str,
    buyer_user_id: int | None = None,
    quantity: int = 1,
) -> InventoryHold:
    """Reserve units for a Stripe Checkout Session. Caller should commit."""
    assert_purchasable(session, listing)
    # Re-check under the same session after assert (handles concurrent writers on SQLite).
    if available_units(session, listing) < quantity:
        raise InventoryError("This listing is sold out or reserved by another checkout")
    hold = InventoryHold(
        listing_id=listing.id,
        buyer_user_id=buyer_user_id,
        stripe_session_id=stripe_session_id,
        quantity=quantity,
        expires_at=utcnow() + timedelta(minutes=HOLD_TTL_MINUTES),
    )
    session.add(hold)
    session.commit()
    session.refresh(hold)
    return hold


def convert_hold(session: Session, stripe_session_id: str | None) -> InventoryHold | None:
    if not stripe_session_id:
        return None
    hold = session.exec(
        select(InventoryHold).where(InventoryHold.stripe_session_id == stripe_session_id)
    ).first()
    if not hold:
        return None
    hold.converted = True
    hold.released = False
    session.add(hold)
    return hold


def release_hold(session: Session, stripe_session_id: str | None) -> None:
    if not stripe_session_id:
        return
    hold = session.exec(
        select(InventoryHold).where(InventoryHold.stripe_session_id == stripe_session_id)
    ).first()
    if hold and not hold.converted:
        hold.released = True
        session.add(hold)
        session.commit()

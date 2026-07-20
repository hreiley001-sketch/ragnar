"""BirdmanOS ride engine — the rollercoaster state machine.

idle → lobby → showcase → bidding → cooldown → archived

Phases advance on elapsed time (checked lazily on every read/tick, so no
background worker is required) or on explicit Command-Hub control. Each phase
entry runs its 'track' actions (the bound API segments):
  - showcase → market-data loop (TCG pricing) sets a live market reference
  - bidding  → opens bids
  - cooldown/archive → declare winner + emit payment_due (no fake capture)

Adaptive tuning: a late bid inside the anti-snipe window extends bidding.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from sqlmodel import Session, select

from . import event_bus, payments, pricing
from .config import settings
from .models import Bid, Listing, Ride, RideStatus, Seller, utcnow

logger = logging.getLogger("ragnar.rides")

DEFAULT_PHASES = [
    {"name": "lobby", "duration_sec": 120},
    {"name": "showcase", "duration_sec": 180},
    {"name": "bidding", "duration_sec": 180},
    {"name": "cooldown", "duration_sec": 60},
]


def phases_of(ride: Ride) -> list:
    return ride.phases or DEFAULT_PHASES


def _duration(ride: Ride, idx: int) -> int:
    ph = phases_of(ride)
    return int(ph[idx].get("duration_sec", 120)) if 0 <= idx < len(ph) else 60


def seconds_left(ride: Ride) -> int | None:
    if not ride.phase_ends_at:
        return None
    return max(0, int((ride.phase_ends_at - utcnow()).total_seconds()))


def min_next_bid_cents(ride: Ride) -> int:
    if ride.current_bid_cents:
        return ride.current_bid_cents + max(
            settings.ride_min_increment_cents, round(ride.current_bid_cents * 0.05)
        )
    return ride.starting_bid_cents or settings.ride_min_increment_cents


# --------------------------------------------------------------------------- #
# Lifecycle
# --------------------------------------------------------------------------- #


def start(session: Session, ride: Ride) -> Ride:
    if not ride.phases:
        ride.phases = DEFAULT_PHASES
    _enter_phase(session, ride, 0)
    session.add(ride)
    session.commit()
    session.refresh(ride)
    return ride


def _enter_phase(session: Session, ride: Ride, idx: int) -> None:
    ph = phases_of(ride)
    name = ph[idx]["name"]
    now = utcnow()
    ride.status = name
    ride.current_phase = name
    ride.phase_index = idx
    ride.phase_started_at = now
    ride.phase_ends_at = now + timedelta(seconds=_duration(ride, idx))
    ride.updated_at = now
    session.add(ride)
    session.commit()
    _run_phase_actions(session, ride, name)
    event_bus.emit(session, "ride_phase_changed", {"phase": name, "title": ride.title}, ride.id)


def _run_phase_actions(session: Session, ride: Ride, name: str) -> None:
    if name == "lobby":
        event_bus.emit(session, "lobby_open", {}, ride.id)
    elif name == "showcase":
        mp = _fetch_market(ride)
        if mp is not None:
            ride.market_price_cents = int(round(mp * 100))
            session.add(ride)
            session.commit()
            event_bus.emit(session, "market_price_fetched", {"market_price": mp}, ride.id)
    elif name == "bidding":
        event_bus.emit(
            session, "bidding_open",
            {"starting_bid": ride.starting_bid_cents / 100, "reserve": ride.reserve_cents / 100},
            ride.id,
        )
    elif name == "cooldown":
        event_bus.emit(session, "cooldown_open", {"top_bid": ride.current_bid_cents / 100}, ride.id)


def _fetch_market(ride: Ride) -> float | None:
    if not ride.listing_id:
        return None
    from .database import engine as _eng  # local import avoids cycle
    with Session(_eng) as s:
        listing = s.get(Listing, ride.listing_id)
    if not listing:
        return None
    query = listing.player_or_character or listing.title
    mp = pricing.market_price(query, category=listing.category)
    return mp.get("market") if mp else None


def tick(session: Session, ride: Ride) -> Ride:
    """Advance any phases whose time has elapsed (lazy scheduler)."""
    if ride.status in (RideStatus.idle.value, RideStatus.archived.value):
        return ride
    guard = 0
    while ride.phase_ends_at and utcnow() >= ride.phase_ends_at and guard < 12:
        guard += 1
        nxt = ride.phase_index + 1
        if nxt >= len(phases_of(ride)):
            _finalize(session, ride)
            break
        _enter_phase(session, ride, nxt)
    session.refresh(ride)
    return ride


def advance(session: Session, ride: Ride) -> Ride:
    """Force the next phase (Command-Hub control)."""
    if ride.status in (RideStatus.idle.value, RideStatus.archived.value):
        return ride
    nxt = ride.phase_index + 1
    if nxt >= len(phases_of(ride)):
        _finalize(session, ride)
    else:
        _enter_phase(session, ride, nxt)
    session.refresh(ride)
    return ride


def _finalize(session: Session, ride: Ride) -> None:
    """Archive the ride and declare a provisional winner.

    Launch safety: do **not** capture payment or mark the listing sold here.
    Live checkout capture is not wired yet — claiming ``payment_captured`` /
    calling ``record_sale`` would invent a paid sale. Emit ``payment_due`` so
    the room UI stays honest until a real Checkout path exists.
    """
    reserve_met = bool(ride.current_bidder) and ride.current_bid_cents >= ride.reserve_cents
    ride.winner = ride.current_bidder if reserve_met else None
    ride.status = RideStatus.archived.value
    ride.current_phase = RideStatus.archived.value
    ride.phase_ends_at = None
    ride.updated_at = utcnow()
    session.add(ride)
    session.commit()

    if ride.winner:
        seller = session.get(Seller, ride.seller_id) if ride.seller_id else None
        split = payments.compute_split(ride.current_bid_cents, seller)
        event_bus.emit(
            session, "payment_due",
            {
                "winner": ride.winner,
                "amount": ride.current_bid_cents / 100,
                "payout_preview": split.as_dict(),
                "message": "Winner declared — payment capture not enabled yet. Listing remains unsold until checkout.",
            },
            ride.id,
        )
        # Pending order for ops visibility only — not paid, listing stays active.
        if ride.listing_id:
            from .models import Order, OrderStatus
            listing = session.get(Listing, ride.listing_id)
            if listing:
                order = Order(
                    listing_id=listing.id,
                    seller_id=listing.seller_id,
                    buyer_name=ride.winner,
                    title=listing.title,
                    price_cents=ride.current_bid_cents,
                    shipping_cents=listing.shipping_cents or 0,
                    status=OrderStatus.pending.value,
                    source="ride",
                )
                session.add(order)
                session.commit()

    event_bus.emit(
        session, "ride_complete",
        {
            "winner": ride.winner,
            "final_price": ride.current_bid_cents / 100,
            "market_price": (ride.market_price_cents or 0) / 100 or None,
            "payment_status": "due" if ride.winner else "none",
        },
        ride.id,
    )


# --------------------------------------------------------------------------- #
# Cars (users) on the track
# --------------------------------------------------------------------------- #


def join(session: Session, ride: Ride) -> Ride:
    ride.viewer_count += 1
    ride.updated_at = utcnow()
    session.add(ride)
    session.commit()
    session.refresh(ride)
    event_bus.emit(session, "user_joined_ride", {"viewer_count": ride.viewer_count}, ride.id)
    return ride


def place_bid(session: Session, ride: Ride, bidder: str, amount_cents: int,
              bidder_user_id: int | None = None) -> Bid:
    tick(session, ride)
    if ride.status != RideStatus.bidding.value:
        raise ValueError("Bidding isn't open on this ride right now.")
    floor = min_next_bid_cents(ride)
    if amount_cents < floor:
        raise ValueError(f"Bid must be at least ${floor / 100:,.2f}.")

    outbid_user_ids: list[int] = []
    for prev in session.exec(select(Bid).where(Bid.ride_id == ride.id, Bid.status == "placed")).all():
        prev.status = "outbid"
        if prev.bidder_user_id and prev.bidder_user_id != bidder_user_id:
            outbid_user_ids.append(prev.bidder_user_id)
        session.add(prev)

    bid = Bid(ride_id=ride.id, bidder=bidder.strip(), amount_cents=amount_cents,
              status="placed", bidder_user_id=bidder_user_id)
    session.add(bid)
    ride.current_bid_cents = amount_cents
    ride.current_bidder = bidder.strip()
    ride.updated_at = utcnow()

    tuned = False
    left = seconds_left(ride)
    if left is not None and left < settings.ride_anti_snipe_seconds:
        ride.phase_ends_at = ride.phase_ends_at + timedelta(seconds=settings.ride_anti_snipe_extend_seconds)
        tuned = True

    session.add(ride)
    session.commit()
    session.refresh(bid)
    session.refresh(ride)

    event_bus.emit(session, "bid_placed", {"bidder": bidder, "amount": amount_cents / 100}, ride.id)
    # eBay-style outbid alerts for signed-in bidders.
    from .notify import notify
    for uid in outbid_user_ids:
        notify(session, uid, "outbid",
               f"You've been outbid on {ride.title}",
               body=f"New high bid: ${amount_cents / 100:,.2f}",
               link=f"/ride/{ride.id}")
    if tuned:
        event_bus.emit(
            session, "ride_tuned",
            {"reason": "anti_snipe", "extended_sec": settings.ride_anti_snipe_extend_seconds},
            ride.id,
        )
    return bid

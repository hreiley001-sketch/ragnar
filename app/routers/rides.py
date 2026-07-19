"""BirdmanOS rides — public ride API + Command Hub control, with SSE live feed."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlmodel import Session, select

from .. import rides_engine as engine
from ..auth import get_current_user
from ..config import settings
from ..database import engine as db_engine
from ..database import get_session
from ..models import Bid, Listing, Ride, RideEvent, RideStatus, Seller
from .admin import require_admin

router = APIRouter(prefix="/api/rides", tags=["rides"])
hub = APIRouter(prefix="/api/hub", tags=["command-hub"])

_ACTIVE = [RideStatus.lobby.value, RideStatus.showcase.value, RideStatus.bidding.value, RideStatus.cooldown.value]


def ride_state(session: Session, ride: Ride) -> dict:
    listing = session.get(Listing, ride.listing_id) if ride.listing_id else None
    seller = session.get(Seller, ride.seller_id) if ride.seller_id else None
    return {
        "id": ride.id,
        "type": ride.type,
        "title": ride.title,
        "status": ride.status,
        "current_phase": ride.current_phase,
        "phase_index": ride.phase_index,
        "phases": engine.phases_of(ride),
        "seconds_left": engine.seconds_left(ride),
        "starting_bid": ride.starting_bid_cents / 100,
        "reserve": ride.reserve_cents / 100,
        "current_bid": ride.current_bid_cents / 100 if ride.current_bid_cents else None,
        "current_bidder": ride.current_bidder,
        "min_next_bid": engine.min_next_bid_cents(ride) / 100,
        "winner": ride.winner,
        "market_price": (ride.market_price_cents / 100) if ride.market_price_cents else None,
        "viewer_count": ride.viewer_count,
        "seller_handle": seller.handle if seller else None,
        "apis": ride.apis or {},
        "listing": None if not listing else {
            "id": listing.id, "title": listing.title, "image_url": listing.image_url,
            "category": listing.category, "grading_company": listing.grading_company,
            "grade": listing.grade, "condition": listing.condition,
        },
    }


def _get_ride(session: Session, ride_id: int) -> Ride:
    ride = session.get(Ride, ride_id)
    if not ride:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")
    return ride


# ------------------------- public ------------------------- #

@router.get("")
def list_rides(session: Session = Depends(get_session)) -> dict:
    rides = session.exec(
        select(Ride).where(Ride.status != RideStatus.archived.value).order_by(Ride.created_at.desc())
    ).all()
    for r in rides:
        engine.tick(session, r)
    return {"items": [ride_state(session, r) for r in rides], "count": len(rides)}


@router.get("/{ride_id}/state")
def get_state(ride_id: int, session: Session = Depends(get_session)) -> dict:
    ride = _get_ride(session, ride_id)
    engine.tick(session, ride)
    events = session.exec(
        select(RideEvent).where(RideEvent.ride_id == ride_id).order_by(RideEvent.id.desc()).limit(15)
    ).all()
    state = ride_state(session, ride)
    state["events"] = [{"id": e.id, "type": e.type, "data": e.data, "at": e.created_at.isoformat()} for e in reversed(events)]
    return state


@router.post("/{ride_id}/join")
def join_ride(ride_id: int, session: Session = Depends(get_session)) -> dict:
    ride = _get_ride(session, ride_id)
    engine.join(session, ride)
    return {"status": "joined", "viewer_count": ride.viewer_count}


@router.post("/{ride_id}/bid")
def place_bid(ride_id: int, payload: dict, session: Session = Depends(get_session),
              user=Depends(get_current_user)) -> dict:
    ride = _get_ride(session, ride_id)
    bidder = (payload.get("bidder") or "").strip()
    if not bidder and user:
        bidder = user.name or user.email.split("@")[0]
    if not bidder:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bidder is required")
    try:
        amount_cents = round(float(payload["amount"]) * 100)
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="amount (dollars) is required")
    try:
        bid = engine.place_bid(session, ride, bidder, amount_cents,
                               bidder_user_id=user.id if user else None)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"status": "ok", "bid_id": bid.id, "current_bid": ride.current_bid_cents / 100,
            "min_next_bid": engine.min_next_bid_cents(ride) / 100, "seconds_left": engine.seconds_left(ride)}


@router.get("/{ride_id}/events")
async def sse_events(ride_id: int, request: Request) -> StreamingResponse:
    """Server-Sent Events: live phase/bid/event stream for a ride."""

    async def gen():
        last_id = 0
        # prime with current state
        with Session(db_engine) as s:
            ride = s.get(Ride, ride_id)
            if not ride:
                yield f"data: {json.dumps({'kind': 'error', 'detail': 'not found'})}\n\n"
                return
            engine.tick(s, ride)
            yield f"data: {json.dumps({'kind': 'state', 'state': ride_state(s, ride)})}\n\n"
        while True:
            if await request.is_disconnected():
                break
            archived = False
            with Session(db_engine) as s:
                ride = s.get(Ride, ride_id)
                if not ride:
                    break
                engine.tick(s, ride)
                new_events = s.exec(
                    select(RideEvent).where(RideEvent.ride_id == ride_id, RideEvent.id > last_id).order_by(RideEvent.id)
                ).all()
                for ev in new_events:
                    last_id = ev.id
                    yield f"data: {json.dumps({'kind': 'event', 'type': ev.type, 'data': ev.data, 'at': ev.created_at.isoformat()})}\n\n"
                yield f"data: {json.dumps({'kind': 'state', 'state': ride_state(s, ride)})}\n\n"
                archived = ride.status == RideStatus.archived.value
            if archived:
                break
            await asyncio.sleep(1.5)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ------------------------- Command Hub (admin) ------------------------- #

_DEFAULT_APIS = {"pricing": "tcg_api", "stream": "livekit", "payments": "stripe_connect", "analytics": "posthog"}


@hub.post("/ride", status_code=status.HTTP_201_CREATED)
def create_ride(payload: dict, session: Session = Depends(get_session), _: None = Depends(require_admin)) -> dict:
    seller = None
    if payload.get("seller_handle"):
        seller = session.exec(select(Seller).where(Seller.handle == str(payload["seller_handle"]).strip().lower())).first()
    ride = Ride(
        type=payload.get("type", "auction"),
        title=payload.get("title", "Live Auction"),
        seller_id=seller.id if seller else None,
        listing_id=payload.get("listing_id"),
        phases=payload.get("phases") or engine.DEFAULT_PHASES,
        apis=payload.get("apis") or _DEFAULT_APIS,
        starting_bid_cents=round(float(payload.get("starting_bid", 0)) * 100),
        reserve_cents=round(float(payload.get("reserve", 0)) * 100),
    )
    session.add(ride)
    session.commit()
    session.refresh(ride)
    return ride_state(session, ride)


@hub.post("/ride/{ride_id}/start")
def start_ride(ride_id: int, session: Session = Depends(get_session), _: None = Depends(require_admin)) -> dict:
    ride = _get_ride(session, ride_id)
    if ride.status != RideStatus.idle.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ride already started")
    engine.start(session, ride)
    return ride_state(session, ride)


@hub.post("/ride/{ride_id}/advance")
def advance_ride(ride_id: int, session: Session = Depends(get_session), _: None = Depends(require_admin)) -> dict:
    ride = _get_ride(session, ride_id)
    engine.advance(session, ride)
    return ride_state(session, ride)


@hub.post("/ride/{ride_id}/tune")
def tune_ride(ride_id: int, payload: dict, session: Session = Depends(get_session), _: None = Depends(require_admin)) -> dict:
    from datetime import timedelta
    ride = _get_ride(session, ride_id)
    changes = {}
    if payload.get("extend_bidding_sec") and ride.phase_ends_at:
        ride.phase_ends_at = ride.phase_ends_at + timedelta(seconds=int(payload["extend_bidding_sec"]))
        changes["extended_sec"] = int(payload["extend_bidding_sec"])
    if payload.get("reserve") is not None:
        ride.reserve_cents = round(float(payload["reserve"]) * 100)
        changes["reserve"] = payload["reserve"]
    if payload.get("starting_bid") is not None:
        ride.starting_bid_cents = round(float(payload["starting_bid"]) * 100)
        changes["starting_bid"] = payload["starting_bid"]
    session.add(ride)
    session.commit()
    from .. import event_bus
    event_bus.emit(session, "ride_tuned", {"reason": "manual", **changes}, ride.id)
    return ride_state(session, ride)


@hub.get("/metrics/ride/{ride_id}")
def ride_metrics(ride_id: int, session: Session = Depends(get_session), _: None = Depends(require_admin)) -> dict:
    ride = _get_ride(session, ride_id)
    engine.tick(session, ride)
    bids = session.exec(select(Bid).where(Bid.ride_id == ride_id).order_by(Bid.created_at)).all()
    unique = len({b.bidder for b in bids})
    velocity = None
    if len(bids) >= 2:
        span = (bids[-1].created_at - bids[0].created_at).total_seconds() / 60 or 1
        velocity = round(len(bids) / span, 2)
    delta_vs_market = None
    if ride.market_price_cents and ride.current_bid_cents:
        delta_vs_market = round((ride.current_bid_cents - ride.market_price_cents) / 100, 2)
    return {
        "ride_id": ride_id, "status": ride.status, "phase": ride.current_phase,
        "viewer_count": ride.viewer_count, "bids": len(bids), "unique_bidders": unique,
        "bid_velocity_per_min": velocity, "current_bid": ride.current_bid_cents / 100 if ride.current_bid_cents else None,
        "market_price": (ride.market_price_cents / 100) if ride.market_price_cents else None,
        "current_vs_market": delta_vs_market, "winner": ride.winner,
    }


@hub.get("/metrics/marketplace")
def marketplace_metrics(session: Session = Depends(get_session), _: None = Depends(require_admin)) -> dict:
    total_rides = session.exec(select(func.count()).select_from(Ride)).one()
    active = session.exec(select(func.count()).select_from(Ride).where(Ride.status.in_(_ACTIVE))).one()
    total_bids = session.exec(select(func.count()).select_from(Bid)).one()
    won = session.exec(select(Ride).where(Ride.winner.is_not(None))).all()
    ride_gmv = round(sum(r.current_bid_cents for r in won) / 100, 2)
    return {
        "rides_total": total_rides, "rides_active": active, "bids_total": total_bids,
        "rides_won": len(won), "ride_gmv": ride_gmv,
    }

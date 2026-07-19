"""Ride social layer — live chat, giveaways, and video tokens (Whatnot parity).

Chat rides on the persisted RideEvent bus: messages are emitted as
``chat_message`` events, and the existing SSE stream at
``/api/rides/{id}/events`` delivers them live — no extra plumbing needed.
Giveaways use the Giveaway/GiveawayEntry tables; video tokens come from the
key-gated LiveKit module.
"""
from __future__ import annotations

import random
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, select

from .. import event_bus, video
from ..auth import can_act_for_seller, get_current_user, is_staff
from ..config import settings
from ..database import get_session
from ..models import Giveaway, GiveawayEntry, Ride, Seller, User

router = APIRouter(prefix="/api/rides", tags=["ride-social"])


# ------------------------- helpers ------------------------- #

def _get_ride(session: Session, ride_id: int) -> Ride:
    ride = session.get(Ride, ride_id)
    if not ride:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")
    return ride


def _display_name(user: Optional[User], payload: dict) -> str:
    """The name shown in chat / giveaway entries: account name (or email
    prefix) for signed-in users, otherwise the name supplied in the payload."""
    if user:
        display = (user.name or user.email.split("@")[0]).strip()[:80]
    else:
        display = (payload.get("name") or "").strip()[:80]
    if not display:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name is required")
    return display


def _host_auth(session: Session, ride: Ride, user: Optional[User], x_store_token: str,
               x_admin_token: str = "") -> bool:
    """True if this request may run the show: staff session, the break-glass
    admin token, or the ride's seller (owner account or store edit token)."""
    if is_staff(user):
        return True
    from ..config import settings
    if settings.admin_token and x_admin_token == settings.admin_token:
        return True
    if ride.seller_id:
        seller = session.get(Seller, ride.seller_id)
        return can_act_for_seller(user, seller, x_store_token)
    return False


def _latest_giveaway(session: Session, ride_id: int, *, only_open: bool = False) -> Optional[Giveaway]:
    stmt = select(Giveaway).where(Giveaway.ride_id == ride_id)
    if only_open:
        stmt = stmt.where(Giveaway.status == "open")
    stmt = stmt.order_by(Giveaway.created_at.desc(), Giveaway.id.desc()).limit(1)
    return session.exec(stmt).first()


def _entry_count(session: Session, giveaway_id: int) -> int:
    return session.exec(
        select(func.count()).select_from(GiveawayEntry).where(
            GiveawayEntry.giveaway_id == giveaway_id
        )
    ).one()


def _giveaway_dict(session: Session, g: Giveaway) -> dict:
    return {
        "id": g.id,
        "title": g.title,
        "status": g.status,
        "winner": g.winner,
        "entries": _entry_count(session, g.id),
    }


# ------------------------- chat ------------------------- #

@router.post("/{ride_id}/chat")
def post_chat(
    ride_id: int,
    payload: dict,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
) -> dict:
    ride = _get_ride(session, ride_id)
    if ride.status in ("idle", "archived"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Ride chat isn't open"
        )
    body = (payload.get("body") or "").strip()
    if not 1 <= len(body) <= 300:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="body must be 1-300 characters"
        )
    display = _display_name(user, payload)
    event_bus.emit(session, "chat_message", {"name": display, "body": body}, ride.id)
    return {"status": "ok"}


# ------------------------- giveaways ------------------------- #

@router.get("/{ride_id}/giveaway")
def get_giveaway(ride_id: int, session: Session = Depends(get_session)) -> dict:
    ride = _get_ride(session, ride_id)
    g = _latest_giveaway(session, ride.id)
    return {"giveaway": _giveaway_dict(session, g) if g else None}


@router.post("/{ride_id}/giveaway/start")
def start_giveaway(
    ride_id: int,
    payload: dict,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
    x_store_token: str = Header(default="", alias="X-Store-Token"),
    x_admin_token: str = Header(default="", alias="X-Admin-Token"),
) -> dict:
    ride = _get_ride(session, ride_id)
    if not _host_auth(session, ride, user, x_store_token, x_admin_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Only the ride host (seller or staff) can start a giveaway",
        )
    title = (payload.get("title") or "").strip()
    if not 2 <= len(title) <= 140:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="title must be 2-140 characters"
        )
    # One open giveaway per ride: cancel any prior open one.
    prior = session.exec(
        select(Giveaway).where(Giveaway.ride_id == ride.id, Giveaway.status == "open")
    ).all()
    for p in prior:
        p.status = "cancelled"
        session.add(p)
    g = Giveaway(ride_id=ride.id, title=title, status="open")
    session.add(g)
    session.commit()
    session.refresh(g)
    event_bus.emit(session, "giveaway_started", {"title": g.title}, ride.id)
    return _giveaway_dict(session, g)


@router.post("/{ride_id}/giveaway/enter")
def enter_giveaway(
    ride_id: int,
    payload: dict,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
) -> dict:
    ride = _get_ride(session, ride_id)
    g = _latest_giveaway(session, ride.id, only_open=True)
    if not g:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No open giveaway")
    display = _display_name(user, payload)
    existing = session.exec(
        select(GiveawayEntry).where(
            GiveawayEntry.giveaway_id == g.id,
            func.lower(GiveawayEntry.name) == display.lower(),
        )
    ).first()
    if existing:
        return {"entered": True, "count": _entry_count(session, g.id)}
    entry = GiveawayEntry(giveaway_id=g.id, name=display, user_id=user.id if user else None)
    session.add(entry)
    session.commit()
    count = _entry_count(session, g.id)
    event_bus.emit(session, "giveaway_entered", {"name": display, "count": count}, ride.id)
    return {"entered": True, "count": count}


@router.post("/{ride_id}/giveaway/draw")
def draw_giveaway(
    ride_id: int,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
    x_store_token: str = Header(default="", alias="X-Store-Token"),
    x_admin_token: str = Header(default="", alias="X-Admin-Token"),
) -> dict:
    ride = _get_ride(session, ride_id)
    if not _host_auth(session, ride, user, x_store_token, x_admin_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Only the ride host (seller or staff) can draw a winner",
        )
    g = _latest_giveaway(session, ride.id, only_open=True)
    if not g:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No open giveaway")
    entries = session.exec(
        select(GiveawayEntry).where(GiveawayEntry.giveaway_id == g.id)
    ).all()
    if not entries:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No entries to draw from")
    winner = random.choice(entries).name
    g.status = "drawn"
    g.winner = winner
    session.add(g)
    session.commit()
    event_bus.emit(session, "giveaway_winner", {"winner": winner, "title": g.title}, ride.id)
    return {"winner": winner}


# ------------------------- video (LiveKit) ------------------------- #

@router.get("/{ride_id}/video-token")
def video_token(
    ride_id: int,
    publish: bool = False,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
    x_store_token: str = Header(default="", alias="X-Store-Token"),
    x_admin_token: str = Header(default="", alias="X-Admin-Token"),
) -> dict:
    ride = _get_ride(session, ride_id)
    if not video.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live video isn't configured yet (set LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET).",
        )
    if user:
        identity = (user.name or user.email.split("@")[0]).strip()[:80] or f"viewer-{secrets.token_hex(3)}"
    else:
        identity = f"viewer-{secrets.token_hex(3)}"
    can_pub = bool(publish) and _host_auth(session, ride, user, x_store_token)
    room = f"ride-{ride.id}"
    return {
        "url": settings.livekit_url,
        "room": room,
        "identity": identity,
        "can_publish": can_pub,
        "token": video.access_token(room, identity, can_publish=can_pub),
    }

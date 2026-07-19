"""Social layer: follows, buyer<->store messages, and public want lists.

All models live in models.py (Follow, Conversation, ChatMessage, WantItem).
Money crosses the API in dollars and is stored as integer cents; timestamps
are naive UTC (models.utcnow) serialized with .isoformat().
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlmodel import Session, select

from ..auth import can_act_for_seller, get_current_user, is_staff, require_user
from ..database import get_session
from ..models import (
    ChatMessage,
    Conversation,
    Follow,
    LiveStream,
    Ride,
    RideStatus,
    Seller,
    User,
    WantItem,
    utcnow,
)
from ..notify import notify, notify_seller

router = APIRouter(prefix="/api/social", tags=["social"])


# --------------------------- helpers --------------------------- #

def _seller_or_404(handle: str, session: Session) -> Seller:
    seller = session.exec(
        select(Seller).where(Seller.handle == (handle or "").strip().lower())
    ).first()
    if not seller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    return seller


def _display(user: Optional[User]) -> str:
    if not user:
        return "Someone"
    return user.name or user.email.split("@")[0]


def _follower_count(session: Session, seller_id: int) -> int:
    return session.exec(
        select(func.count()).select_from(Follow).where(Follow.seller_id == seller_id)
    ).one()


def _is_live(session: Session, seller_id: int) -> bool:
    live = session.exec(
        select(LiveStream.id).where(
            LiveStream.seller_id == seller_id, LiveStream.status == "live"
        ).limit(1)
    ).first()
    if live is not None:
        return True
    bidding = session.exec(
        select(Ride.id).where(
            Ride.seller_id == seller_id, Ride.status == RideStatus.bidding.value
        ).limit(1)
    ).first()
    return bidding is not None


# --------------------------- follows --------------------------- #

class FollowBody(BaseModel):
    handle: str


@router.post("/follow")
def toggle_follow(
    payload: FollowBody,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    seller = _seller_or_404(payload.handle, session)
    existing = session.exec(
        select(Follow).where(Follow.user_id == user.id, Follow.seller_id == seller.id)
    ).first()
    if existing:
        session.delete(existing)
        session.commit()
        following = False
    else:
        session.add(Follow(user_id=user.id, seller_id=seller.id))
        session.commit()
        following = True
        notify_seller(
            session, seller, "new_follower",
            f"{_display(user)} followed your store",
            link=f"/store/{seller.handle}",
        )
    return {"following": following, "followers": _follower_count(session, seller.id)}


@router.get("/follows/mine")
def my_follows(
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    follows = session.exec(
        select(Follow).where(Follow.user_id == user.id).order_by(Follow.created_at.desc())
    ).all()
    items = []
    for f in follows:
        seller = session.get(Seller, f.seller_id)
        if not seller:
            continue
        items.append({
            "handle": seller.handle,
            "display_name": seller.display_name,
            "avatar_url": seller.avatar_url,
            "accent_color": seller.accent_color,
            "is_live": _is_live(session, seller.id),
        })
    return {"items": items}


@router.get("/followers/{handle}")
def follower_count(handle: str, session: Session = Depends(get_session)) -> dict:
    seller = _seller_or_404(handle, session)
    return {"followers": _follower_count(session, seller.id)}


# --------------------------- messages --------------------------- #

class MessageStart(BaseModel):
    handle: str
    body: str = Field(min_length=1, max_length=2000)
    listing_id: Optional[int] = None


class MessageSend(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


def _conv_or_404(session: Session, conv_id: int) -> Conversation:
    conv = session.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conv


def _conv_role(
    session: Session, conv: Conversation, user: Optional[User], x_store_token: str
) -> str:
    """Return 'user' or 'seller' for this participant, or raise 403."""
    if user and user.id == conv.user_id:
        return "user"
    seller = session.get(Seller, conv.seller_id)
    if can_act_for_seller(user, seller, x_store_token):
        return "seller"
    if is_staff(user):
        return "seller"
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Not a participant in this conversation"
    )


@router.post("/messages/start")
def start_conversation(
    payload: MessageStart,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    seller = _seller_or_404(payload.handle, session)
    conv = session.exec(
        select(Conversation).where(
            Conversation.user_id == user.id, Conversation.seller_id == seller.id
        )
    ).first()
    if not conv:
        conv = Conversation(
            user_id=user.id, seller_id=seller.id, listing_id=payload.listing_id
        )
        session.add(conv)
        session.commit()
        session.refresh(conv)
    session.add(ChatMessage(conversation_id=conv.id, sender="user", body=payload.body))
    conv.updated_at = utcnow()
    session.add(conv)
    session.commit()
    notify_seller(
        session, seller, "message_received",
        f"Message from {_display(user)}",
        body=payload.body[:100],
        link="/account#messages",
    )
    return {"conversation_id": conv.id}


@router.get("/messages/mine")
def my_conversations(
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    entries: list[tuple[Conversation, str]] = []  # (conv, side)

    buyer_convs = session.exec(
        select(Conversation).where(Conversation.user_id == user.id)
    ).all()
    entries.extend((c, "buyer") for c in buyer_convs)

    if user.seller_handle:
        my_store = session.exec(
            select(Seller).where(Seller.handle == user.seller_handle)
        ).first()
        if my_store:
            seller_convs = session.exec(
                select(Conversation).where(Conversation.seller_id == my_store.id)
            ).all()
            entries.extend(
                (c, "seller") for c in seller_convs if c.user_id != user.id
            )

    items = []
    for conv, side in entries:
        if side == "buyer":
            other_seller = session.get(Seller, conv.seller_id)
            with_name = other_seller.display_name if other_seller else "Unknown store"
            my_role = "user"
        else:
            buyer = session.get(User, conv.user_id)
            with_name = _display(buyer)
            my_role = "seller"
        last = session.exec(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conv.id)
            .order_by(ChatMessage.id.desc())
            .limit(1)
        ).first()
        unread = session.exec(
            select(func.count()).select_from(ChatMessage).where(
                ChatMessage.conversation_id == conv.id,
                ChatMessage.read == False,  # noqa: E712
                ChatMessage.sender != my_role,
            )
        ).one()
        items.append({
            "id": conv.id,
            "side": side,
            "with": with_name,
            "listing_id": conv.listing_id,
            "last_body": last.body[:120] if last else None,
            "updated_at": conv.updated_at.isoformat(),
            "unread": unread,
        })
    items.sort(key=lambda d: d["updated_at"], reverse=True)
    return {"items": items}


@router.get("/messages/{conv_id}")
def get_conversation(
    conv_id: int,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
    x_store_token: str = Header(default=""),
) -> dict:
    conv = _conv_or_404(session, conv_id)
    my_role = _conv_role(session, conv, user, x_store_token)

    if my_role == "user":
        other_seller = session.get(Seller, conv.seller_id)
        with_name = other_seller.display_name if other_seller else "Unknown store"
    else:
        with_name = _display(session.get(User, conv.user_id))

    unread = session.exec(
        select(ChatMessage).where(
            ChatMessage.conversation_id == conv.id,
            ChatMessage.sender != my_role,
            ChatMessage.read == False,  # noqa: E712
        )
    ).all()
    if unread:
        for m in unread:
            m.read = True
            session.add(m)
        session.commit()

    messages = session.exec(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conv.id)
        .order_by(ChatMessage.id.asc())
    ).all()
    return {
        "id": conv.id,
        "with": with_name,
        "my_role": my_role,
        "messages": [
            {"id": m.id, "sender": m.sender, "body": m.body, "created_at": m.created_at.isoformat()}
            for m in messages
        ],
    }


@router.post("/messages/{conv_id}")
def send_message(
    conv_id: int,
    payload: MessageSend,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
    x_store_token: str = Header(default=""),
) -> dict:
    conv = _conv_or_404(session, conv_id)
    my_role = _conv_role(session, conv, user, x_store_token)

    session.add(ChatMessage(conversation_id=conv.id, sender=my_role, body=payload.body))
    conv.updated_at = utcnow()
    session.add(conv)
    session.commit()

    seller = session.get(Seller, conv.seller_id)
    if my_role == "seller":
        sender_name = seller.display_name if seller else "The store"
        notify(
            session, conv.user_id, "message_received",
            f"Message from {sender_name}",
            body=payload.body[:100],
            link="/account#messages",
        )
    else:
        notify_seller(
            session, seller, "message_received",
            f"Message from {_display(user)}",
            body=payload.body[:100],
            link="/account#messages",
        )
    return {"status": "sent"}


# --------------------------- want lists --------------------------- #

class WantCreate(BaseModel):
    description: str = Field(min_length=3, max_length=300)
    category: Optional[str] = None
    max_price: Optional[float] = Field(default=None, ge=0)


def _want_dict(session: Session, w: WantItem, include_by: bool = False) -> dict:
    d = {
        "id": w.id,
        "description": w.description,
        "category": w.category,
        "max_price": round(w.max_price_cents / 100, 2) if w.max_price_cents is not None else None,
        "status": w.status,
        "created_at": w.created_at.isoformat(),
    }
    if include_by:
        d["by"] = _display(session.get(User, w.user_id))
    return d


@router.post("/wants")
def create_want(
    payload: WantCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    want = WantItem(
        user_id=user.id,
        description=payload.description,
        category=payload.category,
        max_price_cents=round(payload.max_price * 100) if payload.max_price is not None else None,
    )
    session.add(want)
    session.commit()
    session.refresh(want)
    return _want_dict(session, want)


@router.get("/wants")
def list_wants(
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
    mine: bool = Query(False),
) -> dict:
    if mine:
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required"
            )
        wants = session.exec(
            select(WantItem)
            .where(WantItem.user_id == user.id)
            .order_by(WantItem.created_at.desc())
        ).all()
        return {"items": [_want_dict(session, w, include_by=True) for w in wants]}
    wants = session.exec(
        select(WantItem)
        .where(WantItem.status == "open")
        .order_by(WantItem.created_at.desc())
        .limit(100)
    ).all()
    return {"items": [_want_dict(session, w, include_by=True) for w in wants]}


@router.delete("/wants/{want_id}")
def delete_want(
    want_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    want = session.get(WantItem, want_id)
    if not want:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Want not found")
    if want.user_id != user.id and not is_staff(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your want item")
    session.delete(want)
    session.commit()
    return {"status": "deleted"}

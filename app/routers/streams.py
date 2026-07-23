"""Live streams — the 'what's live now' layer for the customer side.

Broadcasting itself needs a video provider (Mux/LiveKit/YouTube/etc.); that plugs
into ``embed_url``. Streams can be scheduled/listed/started without one.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlmodel import Session, select

from .. import auth
from ..config import settings
from ..database import get_session
from ..models import LiveStream, LiveStreamReminder, Seller, User, utcnow
from ..schemas import LiveStreamCreate, LiveStreamRead, LiveStreamUpdate

router = APIRouter(prefix="/api/streams", tags=["streams"])


def _read(stream: LiveStream, seller: Seller) -> LiveStreamRead:
    return LiveStreamRead(
        id=stream.id,
        seller_handle=seller.handle,
        seller_name=seller.display_name,
        avatar_url=seller.avatar_url,
        accent_color=seller.accent_color,
        title=stream.title,
        status=stream.status,
        embed_url=stream.embed_url,
        thumbnail_url=stream.thumbnail_url,
        scheduled_at=stream.scheduled_at,
        started_at=stream.started_at,
        viewer_count=stream.viewer_count,
    )


def _authz(
    seller: Seller,
    user: User | None = None,
    x_store_token: str = "",
    x_admin_token: str = "",
) -> None:
    if settings.admin_token and x_admin_token and x_admin_token == settings.admin_token:
        return
    auth.require_can_act_for_seller(
        user,
        seller,
        x_store_token,
        detail="Sign in as the store owner or provide X-Store-Token to manage streams.",
    )


@router.get("", response_model=list[LiveStreamRead])
def list_streams(
    session: Session = Depends(get_session),
    user: User | None = Depends(auth.get_current_user),
    status_filter: str | None = Query(None, alias="status", description="live | scheduled | ended"),
) -> list[LiveStreamRead]:
    stmt = select(LiveStream)
    if status_filter:
        stmt = stmt.where(LiveStream.status == status_filter)
    else:
        stmt = stmt.where(LiveStream.status.in_(["live", "scheduled"]))
    # Live first, then most viewers / soonest.
    streams = session.exec(stmt).all()
    reminder_ids: set[int] = set()
    if user:
        reminder_ids = {
            r.stream_id for r in session.exec(
                select(LiveStreamReminder).where(LiveStreamReminder.user_id == user.id)
            ).all()
        }

    out = []
    for st in streams:
        seller = session.get(Seller, st.seller_id)
        if seller:
            item = _read(st, seller).model_dump()
            item["is_notifying"] = st.id in reminder_ids
            out.append(item)
    out.sort(key=lambda r: (r.get("status") != "live", -int(r.get("viewer_count") or 0)))
    return out


@router.get("/notify/mine")
def my_notify_stream_ids(
    session: Session = Depends(get_session),
    user: User = Depends(auth.require_user),
) -> dict:
    ids = [
        r.stream_id
        for r in session.exec(select(LiveStreamReminder).where(LiveStreamReminder.user_id == user.id)).all()
    ]
    return {"stream_ids": ids}


@router.post("/{stream_id}/notify")
def toggle_notify(
    stream_id: int,
    payload: dict,
    session: Session = Depends(get_session),
    user: User = Depends(auth.require_user),
) -> dict:
    stream = session.get(LiveStream, stream_id)
    if not stream:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stream not found")
    wants = bool(payload.get("enabled", True))
    existing = session.get(LiveStreamReminder, (user.id, stream_id))
    if wants and not existing:
        session.add(LiveStreamReminder(user_id=user.id, stream_id=stream_id))
    if not wants and existing:
        session.delete(existing)
    session.commit()
    return {"stream_id": stream_id, "enabled": wants}


@router.post("/{handle}", response_model=LiveStreamRead, status_code=status.HTTP_201_CREATED)
def create_stream(
    handle: str,
    payload: LiveStreamCreate,
    session: Session = Depends(get_session),
    user: User | None = Depends(auth.get_current_user),
    x_store_token: str = Header(default=""),
    x_admin_token: str = Header(default=""),
) -> LiveStreamRead:
    seller = session.exec(select(Seller).where(Seller.handle == handle.strip().lower())).first()
    if not seller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    _authz(seller, user, x_store_token, x_admin_token)
    stream = LiveStream(
        seller_id=seller.id,
        title=payload.title.strip(),
        embed_url=payload.embed_url,
        thumbnail_url=payload.thumbnail_url,
        scheduled_at=payload.scheduled_at,
        status=payload.status or "scheduled",
        started_at=utcnow() if payload.status == "live" else None,
    )
    session.add(stream)
    session.commit()
    session.refresh(stream)
    return _read(stream, seller)


@router.patch("/{stream_id}", response_model=LiveStreamRead)
def update_stream(
    stream_id: int,
    payload: LiveStreamUpdate,
    session: Session = Depends(get_session),
    user: User | None = Depends(auth.get_current_user),
    x_store_token: str = Header(default=""),
    x_admin_token: str = Header(default=""),
) -> LiveStreamRead:
    stream = session.get(LiveStream, stream_id)
    if not stream:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stream not found")
    seller = session.get(Seller, stream.seller_id)
    _authz(seller, user, x_store_token, x_admin_token)
    data = payload.model_dump(exclude_unset=True)
    went_live = data.get("status") == "live" and not stream.started_at
    if went_live:
        stream.started_at = utcnow()
    for k, v in data.items():
        setattr(stream, k, v)
    session.add(stream)
    session.commit()
    session.refresh(stream)
    if went_live:
        try:
            from ..automation import emit_bg
            emit_bg("stream.started", {
                "stream_id": stream.id,
                "seller_id": stream.seller_id,
                "seller_handle": seller.handle if seller else None,
                "title": stream.title,
            })
        except Exception:  # noqa: BLE001
            pass
    return _read(stream, seller)

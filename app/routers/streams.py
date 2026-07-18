"""Live streams — the 'what's live now' layer for the customer side.

Broadcasting itself needs a video provider (Mux/LiveKit/YouTube/etc.); that plugs
into ``embed_url``. Streams can be scheduled/listed/started without one.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlmodel import Session, select

from ..config import settings
from ..database import get_session
from ..models import LiveStream, Seller, utcnow
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


def _authz(seller: Seller, x_store_token: str, x_admin_token: str) -> None:
    is_admin = bool(settings.admin_token) and x_admin_token == settings.admin_token
    is_owner = bool(seller.store_edit_token) and x_store_token == seller.store_edit_token
    if not (is_admin or is_owner):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Provide your store token (X-Store-Token) to manage streams.",
        )


@router.get("", response_model=list[LiveStreamRead])
def list_streams(
    session: Session = Depends(get_session),
    status_filter: str | None = Query(None, alias="status", description="live | scheduled | ended"),
) -> list[LiveStreamRead]:
    stmt = select(LiveStream)
    if status_filter:
        stmt = stmt.where(LiveStream.status == status_filter)
    else:
        stmt = stmt.where(LiveStream.status.in_(["live", "scheduled"]))
    # Live first, then most viewers / soonest.
    streams = session.exec(stmt).all()
    out = []
    for st in streams:
        seller = session.get(Seller, st.seller_id)
        if seller:
            out.append(_read(st, seller))
    out.sort(key=lambda r: (r.status != "live", -r.viewer_count))
    return out


@router.post("/{handle}", response_model=LiveStreamRead, status_code=status.HTTP_201_CREATED)
def create_stream(
    handle: str,
    payload: LiveStreamCreate,
    session: Session = Depends(get_session),
    x_store_token: str = Header(default=""),
    x_admin_token: str = Header(default=""),
) -> LiveStreamRead:
    seller = session.exec(select(Seller).where(Seller.handle == handle.strip().lower())).first()
    if not seller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    _authz(seller, x_store_token, x_admin_token)
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
    x_store_token: str = Header(default=""),
    x_admin_token: str = Header(default=""),
) -> LiveStreamRead:
    stream = session.get(LiveStream, stream_id)
    if not stream:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stream not found")
    seller = session.get(Seller, stream.seller_id)
    _authz(seller, x_store_token, x_admin_token)
    data = payload.model_dump(exclude_unset=True)
    if data.get("status") == "live" and not stream.started_at:
        stream.started_at = utcnow()
    for k, v in data.items():
        setattr(stream, k, v)
    session.add(stream)
    session.commit()
    session.refresh(stream)
    return _read(stream, seller)

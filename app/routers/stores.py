"""Customer-facing stores: browse everyone's stores + self-serve customization."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func
from sqlmodel import Session, select

from ..config import settings
from ..database import get_session
from ..models import Listing, ListingStatus, LiveStream, Seller
from ..schemas import ListingRead, StoreProfile, StoreSummary, StoreUpdate

router = APIRouter(prefix="/api/stores", tags=["stores"])


def _seller_or_404(handle: str, session: Session) -> Seller:
    seller = session.exec(
        select(Seller).where(Seller.handle == handle.strip().lower())
    ).first()
    if not seller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    return seller


def _active_count(session: Session, seller_id: int) -> int:
    return session.exec(
        select(func.count()).select_from(Listing).where(
            Listing.seller_id == seller_id,
            Listing.status == ListingStatus.active.value,
        )
    ).one()


def _is_live(session: Session, seller_id: int) -> bool:
    return session.exec(
        select(LiveStream.id).where(
            LiveStream.seller_id == seller_id, LiveStream.status == "live"
        ).limit(1)
    ).first() is not None


def _summary(session: Session, s: Seller) -> dict:
    return {
        "handle": s.handle,
        "display_name": s.display_name,
        "tagline": s.tagline,
        "avatar_url": s.avatar_url,
        "banner_url": s.banner_url,
        "accent_color": s.accent_color,
        "font_family": s.font_family,
        "is_founding": s.is_founding,
        "founding_number": s.founding_number,
        "listing_count": _active_count(session, s.id),
        "is_live": _is_live(session, s.id),
    }


@router.get("", response_model=list[StoreSummary])
def list_stores(
    session: Session = Depends(get_session),
    q: str | None = Query(None, description="Search store name/handle"),
) -> list[StoreSummary]:
    stmt = select(Seller).where(Seller.store_public == True)  # noqa: E712
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where((Seller.display_name.ilike(like)) | (Seller.handle.ilike(like)))
    sellers = session.exec(stmt).all()
    # Live stores first, then Founding, then by inventory.
    summaries = [_summary(session, s) for s in sellers]
    summaries.sort(key=lambda d: (not d["is_live"], not d["is_founding"], -d["listing_count"]))
    return [StoreSummary(**d) for d in summaries]


@router.get("/{handle}", response_model=StoreProfile)
def get_store(handle: str, session: Session = Depends(get_session)) -> StoreProfile:
    s = _seller_or_404(handle, session)
    data = _summary(session, s)
    data["bio"] = s.bio
    return StoreProfile(**data)


@router.get("/{handle}/listings", response_model=list[ListingRead])
def store_listings(
    handle: str,
    session: Session = Depends(get_session),
    include_sold: bool = Query(False),
) -> list[ListingRead]:
    s = _seller_or_404(handle, session)
    stmt = select(Listing).where(Listing.seller_id == s.id)
    if not include_sold:
        stmt = stmt.where(Listing.status == ListingStatus.active.value)
    stmt = stmt.order_by(Listing.created_at.desc())
    return [ListingRead.from_listing(r) for r in session.exec(stmt).all()]


@router.patch("/{handle}", response_model=StoreProfile)
def update_store(
    handle: str,
    payload: StoreUpdate,
    session: Session = Depends(get_session),
    x_store_token: str = Header(default=""),
    x_admin_token: str = Header(default=""),
) -> StoreProfile:
    s = _seller_or_404(handle, session)
    is_admin = bool(settings.admin_token) and x_admin_token == settings.admin_token
    is_owner = bool(s.store_edit_token) and x_store_token == s.store_edit_token
    if not (is_admin or is_owner):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Provide your store edit token (X-Store-Token) to customize this store.",
        )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    session.add(s)
    session.commit()
    session.refresh(s)
    data = _summary(session, s)
    data["bio"] = s.bio
    return StoreProfile(**data)

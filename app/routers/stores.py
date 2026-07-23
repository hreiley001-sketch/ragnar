"""Customer-facing stores: browse everyone's stores + self-serve customization."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func
from sqlmodel import Session, select

from ..auth import get_current_user, require_can_act_for_seller
from ..config import settings
from ..database import get_session
from ..models import Listing, ListingStatus, LiveStream, Seller, User
from ..schemas import ListingRead, StoreProfile, StoreSummary, StoreUpdate

router = APIRouter(prefix="/api/stores", tags=["stores"])


def _seller_or_404(handle: str, session: Session) -> Seller:
    seller = session.exec(
        select(Seller).where(Seller.handle == handle.strip().lower())
    ).first()
    if not seller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    return seller


def _batch_store_stats(
    session: Session, seller_ids: list[int]
) -> tuple[dict[int, int], set[int]]:
    """One grouped count query + one live-id query instead of 2N lookups."""
    if not seller_ids:
        return {}, set()
    counts = {
        sid: int(n)
        for sid, n in session.exec(
            select(Listing.seller_id, func.count())
            .where(
                Listing.seller_id.in_(seller_ids),
                Listing.status == ListingStatus.active.value,
            )
            .group_by(Listing.seller_id)
        ).all()
    }
    live_ids = set(
        session.exec(
            select(LiveStream.seller_id).where(
                LiveStream.seller_id.in_(seller_ids),
                LiveStream.status == "live",
            )
        ).all()
    )
    return counts, live_ids


def _summary(
    s: Seller,
    *,
    listing_count: int = 0,
    is_live: bool = False,
) -> dict:
    from ..media import cdn_url
    return {
        "handle": s.handle,
        "display_name": s.display_name,
        "tagline": s.tagline,
        "avatar_url": s.avatar_url,
        "banner_url": s.banner_url,
        # Optimized (Cloudinary) variants — equal to the originals when unconfigured.
        "avatar_optimized": (cdn_url(s.avatar_url, width=240, height=240) if s.avatar_url else None),
        "banner_optimized": (cdn_url(s.banner_url, width=1200) if s.banner_url else None),
        "accent_color": s.accent_color,
        "font_family": s.font_family,
        "is_founding": s.is_founding,
        "founding_number": s.founding_number,
        "listing_count": listing_count,
        "is_live": is_live,
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
    sellers = list(session.exec(stmt).all())
    counts, live_ids = _batch_store_stats(session, [s.id for s in sellers if s.id is not None])
    # Live stores first, then Founding, then by inventory.
    summaries = [
        _summary(
            s,
            listing_count=counts.get(s.id, 0),
            is_live=s.id in live_ids,
        )
        for s in sellers
    ]
    summaries.sort(key=lambda d: (not d["is_live"], not d["is_founding"], -d["listing_count"]))
    return [StoreSummary(**d) for d in summaries]


@router.get("/{handle}", response_model=StoreProfile)
def get_store(handle: str, session: Session = Depends(get_session)) -> StoreProfile:
    s = _seller_or_404(handle, session)
    counts, live_ids = _batch_store_stats(session, [s.id])
    data = _summary(
        s,
        listing_count=counts.get(s.id, 0),
        is_live=s.id in live_ids,
    )
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
    user: Optional[User] = Depends(get_current_user),
    x_store_token: str = Header(default=""),
    x_admin_token: str = Header(default=""),
) -> StoreProfile:
    s = _seller_or_404(handle, session)
    is_admin = bool(settings.admin_token) and x_admin_token == settings.admin_token
    if not is_admin:
        require_can_act_for_seller(
            user, s, x_store_token,
            detail="Sign in as the store owner or provide X-Store-Token to customize this store.",
        )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    session.add(s)
    session.commit()
    session.refresh(s)
    counts, live_ids = _batch_store_stats(session, [s.id])
    data = _summary(
        s,
        listing_count=counts.get(s.id, 0),
        is_live=s.id in live_ids,
    )
    data["bio"] = s.bio
    return StoreProfile(**data)

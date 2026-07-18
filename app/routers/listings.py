"""Listings: create, search/filter, and fetch a single card.

Structured search is the feature sellers judge RAGNAR against TCGplayer on, so
the query surface here is deliberately rich: free text plus every structured
facet (category, set, condition, grading company, grade floor, price band).
"""
from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlmodel import Session, or_, select

from ..database import get_session
from ..fees import quote
from ..models import (
    Category,
    Condition,
    GradingCompany,
    Listing,
    ListingStatus,
    Seller,
)
from ..payments import compute_split
from ..schemas import ListingCreate, ListingPage, ListingRead, MarkSold, SortOption
from ..services import record_sale

router = APIRouter(prefix="/api/listings", tags=["listings"])


@router.post("", response_model=ListingRead, status_code=status.HTTP_201_CREATED)
def create_listing(
    payload: ListingCreate,
    session: Session = Depends(get_session),
) -> ListingRead:
    # Resolve the seller: a known handle is the source of truth for Founding
    # status, so it can't be spoofed via the request body.
    seller_id = None
    seller_name = payload.seller_name.strip() if payload.seller_name else None
    is_founding = payload.is_founding_seller
    if payload.seller_handle:
        seller = session.exec(
            select(Seller).where(Seller.handle == payload.seller_handle.strip().lower())
        ).first()
        if not seller:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Seller '{payload.seller_handle}' not found. Apply as a seller first.",
            )
        seller_id = seller.id
        seller_name = seller_name or seller.display_name
        is_founding = seller.is_founding

    listing = Listing(
        seller_id=seller_id,
        title=payload.title.strip(),
        category=payload.category.value,
        set_name=payload.set_name.strip() if payload.set_name else None,
        card_number=payload.card_number.strip() if payload.card_number else None,
        player_or_character=(
            payload.player_or_character.strip()
            if payload.player_or_character
            else None
        ),
        year=payload.year,
        is_graded=payload.is_graded,
        condition=payload.condition.value if payload.condition else None,
        grading_company=(
            payload.grading_company.value if payload.grading_company else None
        ),
        grade=payload.grade,
        price_cents=round(payload.price * 100),
        quantity=payload.quantity,
        image_url=payload.image_url.strip() if payload.image_url else None,
        description=payload.description.strip() if payload.description else None,
        seller_name=seller_name,
        is_founding_seller=is_founding,
        status=ListingStatus.active.value,
    )
    session.add(listing)
    session.commit()
    session.refresh(listing)
    return ListingRead.from_listing(listing)


@router.post("/{listing_id}/sell")
def sell_listing(
    listing_id: int,
    payload: MarkSold,
    session: Session = Depends(get_session),
) -> dict:
    """Mark a listing sold. Records a Sale (which becomes a future comp) and, for
    Founding Sellers still in their 0% window, accrues toward the $ cap."""
    listing = session.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    if listing.status == ListingStatus.sold.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Listing already sold")

    price_cents = round(payload.price * 100) if payload.price else listing.price_cents

    sale = record_sale(session, listing, price_cents, source="ragnar")
    session.commit()
    session.refresh(sale)

    seller = session.get(Seller, listing.seller_id) if listing.seller_id else None
    return {
        "status": "sold",
        "listing_id": listing.id,
        "sale_id": sale.id,
        "sold_price": round(price_cents / 100, 2),
        "payout": compute_split(price_cents, seller).as_dict(),
    }


@router.get("", response_model=ListingPage)
def search_listings(
    session: Session = Depends(get_session),
    q: str | None = Query(None, description="Free text (title, player/character, set)"),
    category: Category | None = Query(None),
    set_name: str | None = Query(None),
    condition: Condition | None = Query(None),
    grading_company: GradingCompany | None = Query(None),
    graded: bool | None = Query(None, description="Filter graded vs raw cards"),
    min_grade: float | None = Query(None, ge=1, le=10),
    min_price: float | None = Query(None, ge=0, description="Dollars"),
    max_price: float | None = Query(None, ge=0, description="Dollars"),
    founding_only: bool = Query(False, description="Only Founding Seller listings"),
    sort: SortOption = Query(SortOption.newest),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
) -> ListingPage:
    filters = [Listing.status == ListingStatus.active.value]

    if q:
        like = f"%{q.strip()}%"
        filters.append(
            or_(
                Listing.title.ilike(like),
                Listing.player_or_character.ilike(like),
                Listing.set_name.ilike(like),
            )
        )
    if category:
        filters.append(Listing.category == category.value)
    if set_name:
        filters.append(Listing.set_name.ilike(f"%{set_name.strip()}%"))
    if condition:
        filters.append(Listing.condition == condition.value)
    if grading_company:
        filters.append(Listing.grading_company == grading_company.value)
    if graded is not None:
        filters.append(Listing.is_graded == graded)
    if min_grade is not None:
        filters.append(Listing.grade >= min_grade)
    if min_price is not None:
        filters.append(Listing.price_cents >= round(min_price * 100))
    if max_price is not None:
        filters.append(Listing.price_cents <= round(max_price * 100))
    if founding_only:
        filters.append(Listing.is_founding_seller == True)  # noqa: E712

    total = session.exec(
        select(func.count()).select_from(Listing).where(*filters)
    ).one()

    statement = select(Listing).where(*filters)
    if sort == SortOption.price_asc:
        statement = statement.order_by(Listing.price_cents.asc())
    elif sort == SortOption.price_desc:
        statement = statement.order_by(Listing.price_cents.desc())
    elif sort == SortOption.grade_desc:
        # On SQLite, DESC already sorts NULL grades last, which is what we want.
        statement = statement.order_by(Listing.grade.desc(), Listing.created_at.desc())
    else:  # newest
        statement = statement.order_by(Listing.created_at.desc())

    statement = statement.offset((page - 1) * page_size).limit(page_size)
    rows = session.exec(statement).all()

    return ListingPage(
        items=[ListingRead.from_listing(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)) if total else 0,
    )


@router.get("/{listing_id}", response_model=ListingRead)
def get_listing(
    listing_id: int,
    session: Session = Depends(get_session),
) -> ListingRead:
    listing = session.get(Listing, listing_id)
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found"
        )
    return ListingRead.from_listing(listing)


@router.get("/{listing_id}/fees")
def listing_fees(
    listing_id: int,
    founding_intro: bool = Query(False),
    session: Session = Depends(get_session),
) -> dict:
    """Fee breakdown for this listing's price and seller status."""
    listing = session.get(Listing, listing_id)
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found"
        )
    return quote(
        listing.price_cents / 100,
        is_founding=listing.is_founding_seller,
        founding_intro=founding_intro,
    )

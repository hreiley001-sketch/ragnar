"""Listings: create, search/filter, and fetch a single card.

Structured search is the feature sellers judge RAGNAR against TCGplayer on, so
the query surface here is deliberately rich: free text plus every structured
facet (category, set, condition, grading company, grade floor, price band).

Commerce writes require a signed-in seller (or staff / store token) and bind
listings to the caller's store — clients cannot invent another seller_handle.
"""
from __future__ import annotations

import csv
import io
import math
from typing import Optional

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile, status
from sqlalchemy import func
from sqlmodel import Session, or_, select

from ..auth import (
    get_current_user,
    is_staff,
    require_can_act_for_seller,
    require_user,
)
from ..database import get_session
from ..fees import quote
from ..models import (
    Category,
    Condition,
    GradingCompany,
    Listing,
    ListingStatus,
    Seller,
    User,
)
from ..payments import compute_split
from ..schemas import ListingCreate, ListingPage, ListingRead, ListingUpdate, MarkSold, SortOption
from ..services import record_sale

router = APIRouter(prefix="/api/listings", tags=["listings"])


def _seller_by_handle(session: Session, handle: str) -> Seller:
    seller = session.exec(
        select(Seller).where(Seller.handle == handle.strip().lower())
    ).first()
    if not seller:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Seller '{handle}' not found. Apply as a seller first.",
        )
    return seller


def _resolve_create_seller(
    payload: ListingCreate,
    session: Session,
    user: User,
    x_store_token: str,
) -> Seller:
    """Bind create to the authenticated seller. Staff may target any handle."""
    requested = (payload.seller_handle or "").strip().lower() or None

    if is_staff(user):
        handle = requested or (user.seller_handle or "").strip().lower() or None
        if not handle:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide seller_handle (or link a seller account).",
            )
        seller = _seller_by_handle(session, handle)
        # Staff may act without store token; still allow token path.
        return seller

    handle = (user.seller_handle or "").strip().lower() or None
    if not handle:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Apply as a seller or claim a store before listing.",
        )
    if requested and requested != handle:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create listings for your own store.",
        )
    seller = _seller_by_handle(session, handle)
    require_can_act_for_seller(user, seller, x_store_token)
    return seller


def _listing_seller(session: Session, listing: Listing) -> Seller | None:
    if not listing.seller_id:
        return None
    return session.get(Seller, listing.seller_id)


def _require_listing_owner(
    session: Session,
    listing: Listing,
    user: Optional[User],
    x_store_token: str = "",
) -> Seller:
    seller = _listing_seller(session, listing)
    if not seller:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Listing has no seller owner.",
        )
    require_can_act_for_seller(user, seller, x_store_token)
    return seller


def _persist_listing(payload: ListingCreate, session: Session, seller: Seller) -> ListingRead:
    seller_name = (payload.seller_name or "").strip() or seller.display_name
    listing = Listing(
        seller_id=seller.id,
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
        shipping_cents=round((payload.shipping or 0) * 100),
        quantity=payload.quantity,
        image_url=payload.image_url.strip() if payload.image_url else None,
        description=payload.description.strip() if payload.description else None,
        seller_name=seller_name,
        is_founding_seller=seller.is_founding,
        status=ListingStatus.active.value,
    )
    session.add(listing)
    session.commit()
    session.refresh(listing)

    # Post-create fan-out (never breaks creation): saved-search alerts + follower drops.
    try:
        from .watch import match_new_listing
        match_new_listing(session, listing)
    except Exception:  # noqa: BLE001
        pass
    try:
        from ..notify import notify_followers
        notify_followers(
            session, seller, "new_drop",
            f"New drop from {seller.display_name}: {listing.title}",
            body=f"${listing.price_cents / 100:,.2f}",
            link=f"/listing/{listing.id}",
        )
    except Exception:  # noqa: BLE001
        pass

    return ListingRead.from_listing(listing)


@router.post("", response_model=ListingRead, status_code=status.HTTP_201_CREATED)
def create_listing(
    payload: ListingCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
    x_store_token: str = Header(default=""),
) -> ListingRead:
    seller = _resolve_create_seller(payload, session, user, x_store_token)
    return _persist_listing(payload, session, seller)


def _row_to_payload(row: dict[str, str]) -> dict:
    def _v(name: str) -> str | None:
        val = (row.get(name) or "").strip()
        return val or None

    def _b(name: str, default: bool = False) -> bool:
        raw = _v(name)
        if raw is None:
            return default
        return raw.lower() in {"1", "true", "yes", "on"}

    payload: dict = {
        "title": _v("title"),
        "category": _v("category"),
        "set_name": _v("set_name"),
        "card_number": _v("card_number"),
        "player_or_character": _v("player_or_character"),
        "year": int(_v("year")) if _v("year") else None,
        "is_graded": _b("is_graded", False),
        "condition": _v("condition"),
        "grading_company": _v("grading_company"),
        "grade": float(_v("grade")) if _v("grade") else None,
        "price": float(_v("price")) if _v("price") else None,
        "shipping": float(_v("shipping")) if _v("shipping") else 0,
        "quantity": int(_v("quantity")) if _v("quantity") else 1,
        "image_url": _v("image_url"),
        "description": _v("description"),
        "seller_name": _v("seller_name"),
        "seller_handle": _v("seller_handle"),
        "is_founding_seller": _b("is_founding_seller", False),
    }
    return payload


@router.post("/import/csv")
async def import_listings_csv(
    file: UploadFile = File(..., description="CSV file of listing rows"),
    dry_run: bool = Query(False, description="Validate rows without creating listings"),
    stop_on_error: bool = Query(False, description="Abort import when any row fails validation"),
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
    x_store_token: str = Header(default=""),
) -> dict:
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload a .csv file.")

    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV must be UTF-8 encoded.") from exc

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="CSV must include a header row.")

    created: list[int] = []
    errors: list[dict] = []

    for idx, row in enumerate(reader, start=2):
        try:
            raw_payload = _row_to_payload(row)
            # Non-staff: force every row onto the caller's store.
            if not is_staff(user):
                if not user.seller_handle:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Apply as a seller or claim a store before importing.",
                    )
                raw_payload["seller_handle"] = user.seller_handle
                raw_payload["seller_name"] = raw_payload["seller_name"] or user.seller_handle
            payload = ListingCreate(**raw_payload)
            seller = _resolve_create_seller(payload, session, user, x_store_token)
            if dry_run:
                continue
            listing = _persist_listing(payload, session, seller)
            created.append(listing.id)
        except HTTPException as exc:
            errors.append({"row": idx, "error": exc.detail})
            if stop_on_error and not dry_run:
                break
        except Exception as exc:  # noqa: BLE001
            errors.append({"row": idx, "error": str(exc)})
            if stop_on_error and not dry_run:
                break

    return {
        "status": "ok" if not errors else "partial",
        "dry_run": dry_run,
        "created_count": len(created),
        "created_ids": created,
        "error_count": len(errors),
        "errors": errors,
        "required_columns": ["title", "category", "price", "seller_name or seller_handle"],
    }


@router.patch("/{listing_id}", response_model=ListingRead)
def update_listing(
    listing_id: int,
    payload: ListingUpdate,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
    x_store_token: str = Header(default=""),
) -> ListingRead:
    listing = session.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    _require_listing_owner(session, listing, user, x_store_token)

    data = payload.model_dump(exclude_unset=True)
    if "price" in data and data["price"] is not None:
        listing.price_cents = round(float(data.pop("price")) * 100)
    if "shipping" in data and data["shipping"] is not None:
        listing.shipping_cents = round(float(data.pop("shipping")) * 100)
    for ef in ("category", "condition", "grading_company"):
        if ef not in data:
            continue
        val = data.pop(ef)
        if val is None:
            setattr(listing, ef, None)
        else:
            setattr(listing, ef, val.value if hasattr(val, "value") else val)
    if "status" in data and data["status"] is not None:
        status_val = data.pop("status")
        if status_val not in {s.value for s in ListingStatus}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status")
        listing.status = status_val
    for field, value in data.items():
        if isinstance(value, str) and field in {
            "title", "set_name", "card_number", "player_or_character", "image_url", "description",
        }:
            value = value.strip() if value else None
        setattr(listing, field, value)

    session.add(listing)
    session.commit()
    session.refresh(listing)
    return ListingRead.from_listing(listing)


@router.delete("/{listing_id}")
def delete_listing(
    listing_id: int,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
    x_store_token: str = Header(default=""),
) -> dict:
    listing = session.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    _require_listing_owner(session, listing, user, x_store_token)
    session.delete(listing)
    session.commit()
    return {"status": "deleted", "id": listing_id}


@router.post("/{listing_id}/sell")
def sell_listing(
    listing_id: int,
    payload: MarkSold,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
    x_store_token: str = Header(default=""),
) -> dict:
    """Mark a listing sold. Records a Sale (which becomes a future comp) and,
    for Founding Sellers still within their $250 introductory-rate cap,
    accrues toward it."""
    listing = session.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    if listing.status == ListingStatus.sold.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Listing already sold")

    seller = _require_listing_owner(session, listing, user, x_store_token)

    price_cents = round(payload.price * 100) if payload.price else listing.price_cents

    sale = record_sale(session, listing, price_cents, source="ragnar")

    # Manual sales get an Order record too (offline/agreed sales).
    from ..models import Order
    order = Order(
        listing_id=listing.id, seller_id=listing.seller_id,
        title=listing.title, price_cents=price_cents,
        shipping_cents=listing.shipping_cents or 0,
        status="paid", source="manual",
    )
    session.add(order)
    session.commit()
    session.refresh(sale)
    session.refresh(order)

    return {
        "status": "sold",
        "listing_id": listing.id,
        "sale_id": sale.id,
        "order_id": order.id,
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
    featured: bool = Query(False, description="Only featured/promoted listings"),
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
    if featured:
        filters.append(Listing.is_featured == True)  # noqa: E712

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


@router.get("/{listing_id}/full")
def get_listing_full(
    listing_id: int,
    session: Session = Depends(get_session),
) -> dict:
    """Everything the item page needs in one call: listing + seller + stats."""
    listing = session.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    # Lightweight view analytics (eBay-style "N views") on the item page only.
    listing.view_count = (listing.view_count or 0) + 1
    session.add(listing)
    session.commit()
    session.refresh(listing)
    seller = session.get(Seller, listing.seller_id) if listing.seller_id else None
    data = ListingRead.from_listing(listing).model_dump()
    data["shipping"] = round((listing.shipping_cents or 0) / 100, 2)
    data["is_featured"] = bool(listing.is_featured)
    data["view_count"] = listing.view_count or 0
    data["seller"] = None if not seller else {
        "handle": seller.handle,
        "display_name": seller.display_name,
        "avatar_url": seller.avatar_url,
        "accent_color": seller.accent_color,
        "is_founding": seller.is_founding,
        "founding_number": seller.founding_number,
    }
    return data


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

"""Multi-seller cart + collection ('Add to collection')."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..auth import require_user
from ..database import get_session
from ..fees import quote
from ..models import CartItem, CollectionItem, Listing, ListingStatus, Seller, User

router = APIRouter(prefix="/api/cart", tags=["cart"])
collection_router = APIRouter(prefix="/api/collection", tags=["collection"])


def _listing_line(listing: Listing, seller: Optional[Seller], quantity: int = 1) -> dict:
    price = (listing.price_cents or 0) / 100.0
    is_founding = bool(seller and seller.is_founding)
    fees = quote(price, is_founding=is_founding)
    return {
        "listing_id": listing.id,
        "title": listing.title,
        "price": price,
        "quantity": quantity,
        "image_url": listing.image_url,
        "seller_handle": seller.handle if seller else None,
        "seller_name": seller.display_name if seller else None,
        "is_founding_seller": is_founding,
        "fees": {
            "platform_rate": fees["platform_rate"],
            "platform_fee": fees["platform_fee"],
            "processing_fee": fees["processing_fee"],
            "processing_note": "2.9% + $0.30 card processing",
            "seller_net": fees["seller_net"],
        },
        "line_total": round(price * quantity, 2),
    }


@router.get("")
def get_cart(
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    items = list(session.exec(select(CartItem).where(CartItem.user_id == user.id)).all())
    lines = []
    by_seller: dict[str, list] = {}
    subtotal = 0.0
    for item in items:
        listing = session.get(Listing, item.listing_id)
        if not listing or listing.status != ListingStatus.active.value:
            continue
        seller = session.get(Seller, listing.seller_id) if listing.seller_id else None
        line = _listing_line(listing, seller, item.quantity)
        line["cart_item_id"] = item.id
        lines.append(line)
        handle = line["seller_handle"] or "unknown"
        by_seller.setdefault(handle, []).append(line)
        subtotal += line["line_total"]

    return {
        "items": lines,
        "by_seller": by_seller,
        "subtotal": round(subtotal, 2),
        "item_count": len(lines),
        "checkout_note": "Checkout runs per seller via Stripe Connect. Platform fee 5% (4% Founding) + card processing 2.9% + $0.30.",
    }


class CartAddBody(BaseModel):
    listing_id: int
    quantity: int = Field(default=1, ge=1, le=20)


@router.post("/add")
def add_to_cart(
    payload: CartAddBody,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    listing = session.get(Listing, payload.listing_id)
    if not listing or listing.status != ListingStatus.active.value:
        raise HTTPException(status_code=404, detail="Listing not available")
    existing = session.exec(
        select(CartItem).where(
            CartItem.user_id == user.id, CartItem.listing_id == listing.id
        )
    ).first()
    if existing:
        existing.quantity = min(20, existing.quantity + payload.quantity)
        session.add(existing)
    else:
        session.add(CartItem(user_id=user.id, listing_id=listing.id, quantity=payload.quantity))
    session.commit()
    return get_cart(session=session, user=user)


@router.delete("/{cart_item_id}")
def remove_from_cart(
    cart_item_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    item = session.get(CartItem, cart_item_id)
    if not item or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Cart item not found")
    session.delete(item)
    session.commit()
    return get_cart(session=session, user=user)


class CollectionAddBody(BaseModel):
    listing_id: Optional[int] = None
    title: str = Field(min_length=1, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=500)


@collection_router.get("")
def list_collection(
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    items = list(session.exec(
        select(CollectionItem).where(CollectionItem.user_id == user.id).order_by(CollectionItem.created_at.desc())
    ).all())
    return {
        "items": [
            {
                "id": i.id,
                "listing_id": i.listing_id,
                "title": i.title,
                "notes": i.notes,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            }
            for i in items
        ]
    }


@collection_router.post("/add")
def add_to_collection(
    payload: CollectionAddBody,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    title = payload.title.strip()
    if payload.listing_id:
        listing = session.get(Listing, payload.listing_id)
        if listing:
            title = listing.title
    item = CollectionItem(
        user_id=user.id,
        listing_id=payload.listing_id,
        title=title,
        notes=payload.notes,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return {"ok": True, "id": item.id, "title": item.title}

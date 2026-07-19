"""eBay-style Best Offers: buyers propose a price on a listing, sellers
accept/decline/counter, and buyers respond to counters.

Money follows the house rule — integer cents in the DB, dollars over the API.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlmodel import Session, select

from ..auth import can_act_for_seller, get_current_user, is_staff, require_user
from ..database import get_session
from ..models import Listing, ListingStatus, Offer, OfferStatus, Seller, User, utcnow
from ..notify import notify, notify_seller

router = APIRouter(prefix="/api/offers", tags=["offers"])

_NEGOTIABLE = (OfferStatus.open.value, OfferStatus.countered.value)


# --------------------------- helpers --------------------------- #

def _offer_dict(session: Session, o: Offer) -> dict:
    listing = session.get(Listing, o.listing_id)
    buyer = session.get(User, o.buyer_user_id)
    buyer_name = None
    if buyer:
        buyer_name = buyer.name or (buyer.email or "").split("@")[0]
    return {
        "id": o.id,
        "listing_id": o.listing_id,
        "listing_title": listing.title if listing else None,
        "listing_image": listing.image_url if listing else None,
        "listing_price": round(listing.price_cents / 100, 2) if listing else None,
        "amount": round(o.amount_cents / 100, 2),
        "counter_amount": (
            round(o.counter_amount_cents / 100, 2)
            if o.counter_amount_cents is not None else None
        ),
        "message": o.message,
        "status": o.status,
        "created_at": o.created_at.isoformat(),
        "buyer_name": buyer_name,
    }


def _offer_or_404(session: Session, offer_id: int) -> Offer:
    offer = session.get(Offer, offer_id)
    if not offer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
    return offer


def _listing_title(session: Session, offer: Offer) -> str:
    listing = session.get(Listing, offer.listing_id)
    return listing.title if listing else "your listing"


def _dollars(cents: int) -> str:
    return f"${cents / 100:,.2f}"


# --------------------------- buyer: make an offer --------------------------- #

@router.post("")
def make_offer(
    payload: dict,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    listing = session.get(Listing, payload.get("listing_id") or 0)
    if not listing or listing.status != ListingStatus.active.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Listing not found or not active",
        )
    try:
        amount = float(payload["amount"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="amount (dollars) is required")
    if not (0 < amount <= 1_000_000):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="amount must be between $0 and $1,000,000")
    message = (str(payload.get("message") or "").strip() or None)
    if message:
        message = message[:500]

    # One live negotiation per buyer per listing — refresh in place, no dupes.
    offer = session.exec(
        select(Offer).where(
            Offer.listing_id == listing.id,
            Offer.buyer_user_id == user.id,
            Offer.status.in_(_NEGOTIABLE),
        )
    ).first()
    if offer:
        offer.amount_cents = round(amount * 100)
        offer.message = message
        offer.status = OfferStatus.open.value
        offer.counter_amount_cents = None
        offer.updated_at = utcnow()
    else:
        offer = Offer(
            listing_id=listing.id,
            seller_id=listing.seller_id,
            buyer_user_id=user.id,
            amount_cents=round(amount * 100),
            message=message,
        )
    session.add(offer)
    session.commit()
    session.refresh(offer)

    seller = session.get(Seller, listing.seller_id) if listing.seller_id else None
    notify_seller(
        session, seller, "offer_received",
        f"New offer on {listing.title}",
        body=_dollars(offer.amount_cents),
        link=f"/listing/{listing.id}",
    )
    return _offer_dict(session, offer)


# --------------------------- buyer: my offers --------------------------- #

@router.get("/mine")
def my_offers(
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    offers = session.exec(
        select(Offer).where(Offer.buyer_user_id == user.id).order_by(Offer.created_at.desc())
    ).all()
    return {"items": [_offer_dict(session, o) for o in offers]}


# --------------------------- seller: offers on my store --------------------------- #

@router.get("/store/{handle}")
def store_offers(
    handle: str,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
    x_store_token: str = Header(default="", alias="X-Store-Token"),
) -> dict:
    seller = session.exec(
        select(Seller).where(Seller.handle == handle.strip().lower())
    ).first()
    if not seller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    if not can_act_for_seller(user, seller, x_store_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Not authorized for this store")
    offers = session.exec(
        select(Offer).where(Offer.seller_id == seller.id).order_by(Offer.created_at.desc())
    ).all()
    return {"items": [_offer_dict(session, o) for o in offers]}


# --------------------------- seller: respond --------------------------- #

@router.post("/{offer_id}/respond")
def respond_to_offer(
    offer_id: int,
    payload: dict,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
    x_store_token: str = Header(default="", alias="X-Store-Token"),
) -> dict:
    offer = _offer_or_404(session, offer_id)
    seller = session.get(Seller, offer.seller_id) if offer.seller_id else None
    # Orphaned offers (no seller) are staff-only; can_act_for_seller(None) is False.
    if not (is_staff(user) or can_act_for_seller(user, seller, x_store_token)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Not authorized to respond to this offer")
    if offer.status not in _NEGOTIABLE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Offer is already {offer.status}")

    action = str(payload.get("action") or "").strip().lower()
    title = _listing_title(session, offer)

    if action == "accept":
        offer.status = OfferStatus.accepted.value
        notify(
            session, offer.buyer_user_id, "offer_accepted",
            f"Offer accepted — {title}",
            body="Pay now to complete your order.",
            link=f"/listing/{offer.listing_id}?offer={offer.id}",
        )
    elif action == "decline":
        offer.status = OfferStatus.declined.value
        notify(
            session, offer.buyer_user_id, "offer_declined",
            f"Offer declined — {title}",
            link=f"/listing/{offer.listing_id}",
        )
    elif action == "counter":
        try:
            counter_amount = float(payload["counter_amount"])
        except (KeyError, TypeError, ValueError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="counter_amount (dollars) is required")
        if counter_amount <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="counter_amount must be > 0")
        offer.counter_amount_cents = round(counter_amount * 100)
        offer.status = OfferStatus.countered.value
        notify(
            session, offer.buyer_user_id, "offer_countered",
            f"Counter offer — {title}",
            body=f"Seller countered at {_dollars(offer.counter_amount_cents)}.",
            link=f"/listing/{offer.listing_id}",
        )
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="action must be accept, decline, or counter")

    offer.updated_at = utcnow()
    session.add(offer)
    session.commit()
    session.refresh(offer)
    return _offer_dict(session, offer)


# --------------------------- buyer: respond to a counter --------------------------- #

@router.post("/{offer_id}/buyer-respond")
def buyer_respond(
    offer_id: int,
    payload: dict,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    offer = _offer_or_404(session, offer_id)
    if offer.buyer_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="This offer belongs to another buyer")
    if offer.status != OfferStatus.countered.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Only countered offers can be responded to")

    action = str(payload.get("action") or "").strip().lower()
    seller = session.get(Seller, offer.seller_id) if offer.seller_id else None
    title = _listing_title(session, offer)

    if action == "accept":
        # Agreed price becomes the seller's counter.
        offer.amount_cents = offer.counter_amount_cents or offer.amount_cents
        offer.status = OfferStatus.accepted.value
        notify_seller(
            session, seller, "offer_accepted",
            f"Counter accepted — {title}",
            body=f"Buyer accepted your counter of {_dollars(offer.amount_cents)}.",
            link=f"/listing/{offer.listing_id}",
        )
    elif action == "decline":
        offer.status = OfferStatus.declined.value
        notify_seller(
            session, seller, "offer_declined",
            f"Counter declined — {title}",
            link=f"/listing/{offer.listing_id}",
        )
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="action must be accept or decline")

    offer.updated_at = utcnow()
    session.add(offer)
    session.commit()
    session.refresh(offer)
    return _offer_dict(session, offer)

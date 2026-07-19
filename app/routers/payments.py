"""Stripe Connect endpoints: seller onboarding, checkout, and webhooks."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session, select  # noqa: F401  (select used in webhook)

from .. import payments
from ..database import get_session
from ..models import Listing, ListingStatus, Seller
from ..services import record_sale

logger = logging.getLogger("ragnar.payments")
router = APIRouter(prefix="/api/payments", tags=["payments"])


def _seller_or_404(handle: str, session: Session) -> Seller:
    seller = session.exec(
        select(Seller).where(Seller.handle == handle.strip().lower())
    ).first()
    if not seller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seller not found")
    return seller


@router.get("/status")
def payments_status() -> dict:
    return payments.status()


@router.post("/connect/{handle}")
def connect_account(handle: str, session: Session = Depends(get_session)) -> dict:
    """Create (if needed) the seller's Stripe Express account and return an
    onboarding link for them to finish setup."""
    seller = _seller_or_404(handle, session)
    try:
        account_id = payments.ensure_connect_account(session, seller)
        url = payments.onboarding_link(account_id)
    except payments.PaymentsError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    return {"account_id": account_id, "onboarding_url": url}


@router.get("/connect/{handle}/status")
def connect_status(handle: str, session: Session = Depends(get_session)) -> dict:
    seller = _seller_or_404(handle, session)
    try:
        return payments.refresh_account_status(session, seller)
    except payments.PaymentsError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))


@router.post("/checkout/{listing_id}")
def checkout(listing_id: int, payload: dict | None = None,
             session: Session = Depends(get_session)) -> dict:
    """Create a Checkout Session so a buyer can purchase this listing.

    Pass {"offer_id": N} to pay an accepted Best Offer price instead of the
    listing price.
    """
    listing = session.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    if listing.status != ListingStatus.active.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Listing is not active")
    seller = session.get(Seller, listing.seller_id) if listing.seller_id else None

    amount_override = None
    offer_id = (payload or {}).get("offer_id")
    if offer_id:
        from ..models import Offer, OfferStatus
        offer = session.get(Offer, int(offer_id))
        if not offer or offer.listing_id != listing.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found for this listing")
        if offer.status != OfferStatus.accepted.value:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Offer isn't accepted")
        amount_override = offer.counter_amount_cents or offer.amount_cents
    try:
        return payments.create_checkout_session(listing, seller, amount_cents=amount_override)
    except payments.PaymentsError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))


@router.post("/webhook")
async def webhook(request: Request, session: Session = Depends(get_session)) -> dict:
    """Stripe webhook receiver. On checkout.session.completed, mark the listing
    sold and record the comp."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = payments.construct_event(payload, sig)
    except payments.PaymentsError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:  # signature/parse failure
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid webhook: {e}")

    if event["type"] == "checkout.session.completed":
        obj = event["data"]["object"]
        listing_id = (obj.get("metadata") or {}).get("listing_id")
        amount_total = obj.get("amount_total")
        if listing_id:
            listing = session.get(Listing, int(listing_id))
            if listing and listing.status == ListingStatus.active.value:
                price_cents = int(amount_total) if amount_total else listing.price_cents
                record_sale(session, listing, price_cents, source="stripe")

                # Create the Order record buyers/sellers manage post-checkout.
                from ..emailer import ops_alert
                from ..models import Order, User
                from ..notify import notify, notify_seller
                details = obj.get("customer_details") or {}
                buyer_email = (details.get("email") or "").lower() or None
                buyer_user = None
                if buyer_email:
                    buyer_user = session.exec(select(User).where(User.email == buyer_email)).first()
                order = Order(
                    listing_id=listing.id,
                    seller_id=listing.seller_id,
                    buyer_user_id=buyer_user.id if buyer_user else None,
                    buyer_name=details.get("name"),
                    buyer_email=buyer_email,
                    title=listing.title,
                    price_cents=max(0, price_cents - (listing.shipping_cents or 0)),
                    shipping_cents=listing.shipping_cents or 0,
                    status="paid",
                    stripe_session_id=obj.get("id"),
                    source="stripe",
                )
                session.add(order)
                session.commit()
                session.refresh(order)
                seller = session.get(Seller, listing.seller_id) if listing.seller_id else None
                notify_seller(session, seller, "order_paid",
                              f"Order paid — {listing.title}",
                              body=f"${price_cents / 100:,.2f} · ship it and add tracking.",
                              link="/account#store")
                if buyer_user:
                    notify(session, buyer_user.id, "order_paid",
                           f"Order confirmed — {listing.title}",
                           body="You'll get tracking once it ships.", link="/account#orders")
                ops_alert(f"Order paid: {listing.title} (${price_cents / 100:,.2f})")
                logger.info("Listing %s sold via Stripe; order %s created", listing_id, order.id)

    return {"received": True}

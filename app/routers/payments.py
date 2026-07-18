"""Stripe Connect endpoints: seller onboarding, checkout, and webhooks."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session, select

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
def checkout(listing_id: int, session: Session = Depends(get_session)) -> dict:
    """Create a Checkout Session so a buyer can purchase this listing."""
    listing = session.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    if listing.status != ListingStatus.active.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Listing is not active")
    seller = session.get(Seller, listing.seller_id) if listing.seller_id else None
    try:
        return payments.create_checkout_session(listing, seller)
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
                session.commit()
                logger.info("Listing %s marked sold via Stripe checkout", listing_id)

    return {"received": True}

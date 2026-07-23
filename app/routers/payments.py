"""Stripe Connect endpoints: seller onboarding, checkout, and webhooks.

Commerce write paths require authentication:
- Connect onboarding: store owner / staff / store token
- Checkout: signed-in buyer

Webhook processing is idempotent via ProcessedStripeEvent + stripe_session_id.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlmodel import Session, select

from .. import inventory, payments
from ..auth import get_current_user, require_can_act_for_seller, require_user
from ..database import get_session
from ..models import Listing, ListingStatus, Order, ProcessedStripeEvent, Seller, User
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
def connect_account(
    handle: str,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
    x_store_token: str = Header(default=""),
) -> dict:
    """Create (if needed) the seller's Stripe Express account and return an
    onboarding link for them to finish setup."""
    seller = _seller_or_404(handle, session)
    require_can_act_for_seller(user, seller, x_store_token)
    try:
        account_id = payments.ensure_connect_account(session, seller)
        url = payments.onboarding_link(account_id)
    except payments.PaymentsError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    return {"account_id": account_id, "onboarding_url": url}


@router.get("/connect/{handle}/status")
def connect_status(
    handle: str,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
    x_store_token: str = Header(default=""),
) -> dict:
    seller = _seller_or_404(handle, session)
    require_can_act_for_seller(user, seller, x_store_token)
    try:
        return payments.refresh_account_status(session, seller)
    except payments.PaymentsError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))


@router.post("/checkout/{listing_id}")
def checkout(
    listing_id: int,
    request: Request,
    payload: dict | None = None,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    """Create a Checkout Session so a signed-in buyer can purchase this listing.

    Pass {"offer_id": N} to pay an accepted Best Offer price instead of the
    listing price. Reserves inventory until the session expires or pays.
    """
    from .. import ratelimit
    ip = ratelimit.client_ip(request)
    ratelimit.limiter.hit(
        f"checkout:user:{user.id}",
        limit=ratelimit.CHECKOUT_LIMIT,
        window_seconds=ratelimit.CHECKOUT_WINDOW,
    )
    ratelimit.limiter.hit(
        f"checkout:ip:{ip}",
        limit=ratelimit.CHECKOUT_LIMIT,
        window_seconds=ratelimit.CHECKOUT_WINDOW,
    )
    listing = session.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    try:
        inventory.assert_purchasable(session, listing)
    except inventory.InventoryError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    seller = session.get(Seller, listing.seller_id) if listing.seller_id else None
    if seller:
        from .. import trust as trust_svc
        trust_svc.assert_can_sell(seller)

    amount_override = None
    offer_id = (payload or {}).get("offer_id")
    if offer_id:
        from ..models import Offer, OfferStatus
        offer = session.get(Offer, int(offer_id))
        if not offer or offer.listing_id != listing.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found for this listing")
        if offer.status != OfferStatus.accepted.value:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Offer isn't accepted")
        if offer.buyer_user_id and offer.buyer_user_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This offer belongs to another buyer")
        amount_override = offer.counter_amount_cents or offer.amount_cents
    try:
        result = payments.create_checkout_session(
            listing, seller, amount_cents=amount_override, buyer_user_id=user.id,
        )
    except payments.PaymentsError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))

    try:
        inventory.create_hold(
            session, listing,
            stripe_session_id=result["id"],
            buyer_user_id=user.id,
        )
    except inventory.InventoryError as e:
        # Race: another buyer reserved the last unit between assert and hold.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return result


def _already_processed(session: Session, event_id: str) -> bool:
    return session.get(ProcessedStripeEvent, event_id) is not None


def _mark_processed(session: Session, event_id: str, event_type: str) -> None:
    session.add(ProcessedStripeEvent(event_id=event_id, event_type=event_type))
    session.commit()


def _order_for_session(session: Session, stripe_session_id: str | None) -> Order | None:
    if not stripe_session_id:
        return None
    return session.exec(
        select(Order).where(Order.stripe_session_id == stripe_session_id)
    ).first()


def _handle_checkout_completed(session: Session, obj: dict) -> None:
    session_id = obj.get("id")
    if _order_for_session(session, session_id):
        logger.info("Skipping duplicate order for Stripe session %s", session_id)
        inventory.convert_hold(session, session_id)
        session.commit()
        return

    listing_id = (obj.get("metadata") or {}).get("listing_id")
    amount_total = obj.get("amount_total")
    if not listing_id:
        return

    listing = session.get(Listing, int(listing_id))
    if not listing:
        logger.warning("Webhook listing %s missing", listing_id)
        return

    # Convert hold first so available units don't block finalization.
    inventory.convert_hold(session, session_id)

    if listing.status == ListingStatus.sold.value and (listing.quantity or 0) <= 0:
        # Already fully sold — still record order if missing (shouldn't happen).
        if _order_for_session(session, session_id):
            session.commit()
            return

    price_cents = int(amount_total) if amount_total else listing.price_cents
    # Only decrement inventory / mark sold when still active with stock.
    if listing.status == ListingStatus.active.value and (listing.quantity or 0) > 0:
        record_sale(session, listing, price_cents, source="stripe")
    elif listing.status == ListingStatus.active.value:
        # Quantity already 0 but status lag — mark sold without extra Sale if needed.
        listing.status = ListingStatus.sold.value
        session.add(listing)

    from ..emailer import ops_alert
    from ..notify import notify, notify_seller

    details = obj.get("customer_details") or {}
    buyer_email = (details.get("email") or "").lower() or None
    meta = obj.get("metadata") or {}
    buyer_user = None
    buyer_user_id = meta.get("buyer_user_id")
    if buyer_user_id:
        buyer_user = session.get(User, int(buyer_user_id))
    if not buyer_user and buyer_email:
        buyer_user = session.exec(select(User).where(User.email == buyer_email)).first()

    order = Order(
        listing_id=listing.id,
        seller_id=listing.seller_id,
        buyer_user_id=buyer_user.id if buyer_user else None,
        buyer_name=details.get("name") or (buyer_user.name if buyer_user else None),
        buyer_email=buyer_email or (buyer_user.email if buyer_user else None),
        title=listing.title,
        price_cents=max(0, price_cents - (listing.shipping_cents or 0)),
        shipping_cents=listing.shipping_cents or 0,
        status="paid",
        stripe_session_id=session_id,
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

    try:
        from ..automation import emit_bg
        emit_bg("order.paid", {
            "order_id": order.id,
            "listing_id": listing.id,
            "title": listing.title,
            "price_cents": price_cents,
            "seller_id": listing.seller_id,
            "buyer_user_id": order.buyer_user_id,
            "stripe_session_id": session_id,
            "source": "stripe",
        })
        emit_bg("listing.sold", {
            "listing_id": listing.id,
            "order_id": order.id,
            "title": listing.title,
            "price_cents": price_cents,
            "source": "stripe",
        })
    except Exception:  # noqa: BLE001
        pass


@router.post("/webhook")
async def webhook(request: Request, session: Session = Depends(get_session)) -> dict:
    """Stripe webhook receiver. Idempotent on event.id and checkout session id."""
    from sqlalchemy.exc import IntegrityError

    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = payments.construct_event(payload, sig)
    except payments.PaymentsError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:  # signature/parse failure
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid webhook: {e}")

    event_id = event.get("id") or ""
    event_type = event.get("type") or ""
    if event_id and _already_processed(session, event_id):
        return {"received": True, "duplicate": True}

    # Claim the event id BEFORE side effects so concurrent workers can't double-run.
    if event_id:
        try:
            _mark_processed(session, event_id, event_type or "unknown")
        except IntegrityError:
            session.rollback()
            return {"received": True, "duplicate": True}
        except Exception:  # noqa: BLE001
            session.rollback()
            if _already_processed(session, event_id):
                return {"received": True, "duplicate": True}
            raise

    try:
        if event_type == "checkout.session.completed":
            _handle_checkout_completed(session, event["data"]["object"])
        elif event_type == "checkout.session.expired":
            obj = event["data"]["object"]
            inventory.release_hold(session, obj.get("id"))
            session.commit()
    except IntegrityError:
        # Unique stripe_session_id (or similar) — treat as already fulfilled.
        session.rollback()
        return {"received": True, "duplicate": True}

    return {"received": True}

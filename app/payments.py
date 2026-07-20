"""Payments — Stripe Connect (Express) for a marketplace.

Money flow (destination charge, per the business model doc's Section 7.1):
  buyer pays via Stripe Checkout → funds are transferred to the seller's connected
  account, minus RAGNAR's ``application_fee_amount`` (the platform fee). Stripe's
  processing fee is separate.

Everything is **key-gated**: with no STRIPE_SECRET_KEY set, `configured()` is
False and the routes return 503. Nothing here moves money on its own — a real
charge only happens when a buyer completes Checkout with your live/test keys.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass

from sqlmodel import Session

from .config import settings
from .models import Listing, Seller
from .services import effective_platform_rate

logger = logging.getLogger("ragnar.payments")


class PaymentsError(RuntimeError):
    """Raised for payment-config or Stripe API problems (router maps to HTTP)."""


# --------------------------------------------------------------------------- #
# Fee / payout math (also used by the /sell endpoint and Stripe app fee)
# --------------------------------------------------------------------------- #


@dataclass
class PayoutSplit:
    gross_cents: int
    platform_fee_cents: int
    processing_fee_cents: int
    seller_payout_cents: int
    platform_rate: float

    def as_dict(self) -> dict:
        d = asdict(self)
        d["gross"] = round(self.gross_cents / 100, 2)
        d["platform_fee"] = round(self.platform_fee_cents / 100, 2)
        d["processing_fee"] = round(self.processing_fee_cents / 100, 2)
        d["seller_payout"] = round(self.seller_payout_cents / 100, 2)
        return d


def compute_split(gross_cents: int, seller=None) -> PayoutSplit:
    rate = effective_platform_rate(seller)
    platform_fee = round(gross_cents * rate)
    processing = round(gross_cents * settings.processing_rate + settings.processing_flat * 100)
    payout = gross_cents - platform_fee - processing
    return PayoutSplit(
        gross_cents=gross_cents,
        platform_fee_cents=platform_fee,
        processing_fee_cents=processing,
        seller_payout_cents=payout,
        platform_rate=rate,
    )


# --------------------------------------------------------------------------- #
# Stripe client
# --------------------------------------------------------------------------- #


def configured() -> bool:
    return bool(settings.stripe_secret_key)


def status() -> dict:
    return {
        "live": settings.payments_live and configured(),
        "configured": configured(),
        "provider": "stripe_connect",
        "mode": "live" if settings.stripe_secret_key.startswith("sk_live") else "test",
        "webhook_configured": bool(settings.stripe_webhook_secret),
        "currency": settings.platform_currency,
        "note": None if configured() else
        "Set STRIPE_SECRET_KEY (test key sk_test_… is fine) to enable payments.",
    }


def _stripe():
    if not configured():
        raise PaymentsError(
            "Stripe is not configured. Add STRIPE_SECRET_KEY to your .env "
            "(a test key sk_test_… works for end-to-end testing)."
        )
    import stripe  # imported lazily so the app runs without the key

    stripe.api_key = settings.stripe_secret_key
    return stripe


# --------------------------------------------------------------------------- #
# Connect onboarding (sellers get paid)
# --------------------------------------------------------------------------- #


def ensure_connect_account(session: Session, seller: Seller) -> str:
    """Return the seller's Stripe connected-account id, creating one if needed."""
    if seller.stripe_account_id:
        return seller.stripe_account_id
    stripe = _stripe()
    account = stripe.Account.create(
        type="express",
        email=seller.email or None,
        capabilities={
            "card_payments": {"requested": True},
            "transfers": {"requested": True},
        },
        business_profile={"name": seller.display_name},
        metadata={"ragnar_seller_handle": seller.handle},
    )
    seller.stripe_account_id = account.id
    session.add(seller)
    session.commit()
    session.refresh(seller)
    return account.id


def onboarding_link(account_id: str) -> str:
    stripe = _stripe()
    base = settings.public_base_url
    link = stripe.AccountLink.create(
        account=account_id,
        refresh_url=f"{base}/?stripe=refresh",
        return_url=f"{base}/?stripe=return",
        type="account_onboarding",
    )
    return link.url


def refresh_account_status(session: Session, seller: Seller) -> dict:
    if not seller.stripe_account_id:
        return {"connected": False, "charges_enabled": False, "payouts_enabled": False, "details_submitted": False}
    stripe = _stripe()
    acct = stripe.Account.retrieve(seller.stripe_account_id)
    seller.stripe_charges_enabled = bool(acct.get("charges_enabled"))
    session.add(seller)
    session.commit()
    return {
        "connected": True,
        "account_id": seller.stripe_account_id,
        "charges_enabled": bool(acct.get("charges_enabled")),
        "payouts_enabled": bool(acct.get("payouts_enabled")),
        "details_submitted": bool(acct.get("details_submitted")),
    }


# --------------------------------------------------------------------------- #
# Checkout (buyers pay)
# --------------------------------------------------------------------------- #


def create_checkout_session(listing: Listing, seller: Seller | None,
                            amount_cents: int | None = None,
                            buyer_user_id: int | None = None) -> dict:
    """Create a Stripe Checkout Session for a listing using a destination charge
    with RAGNAR's platform fee as the application fee. ``amount_cents`` overrides
    the listing price (accepted Best Offers). Shipping is added on top."""
    if not seller or not seller.stripe_account_id:
        raise PaymentsError("This seller hasn't connected a Stripe payout account yet.")
    if not seller.stripe_charges_enabled:
        raise PaymentsError("Seller's Stripe onboarding is incomplete (charges not enabled).")

    stripe = _stripe()
    price_cents = amount_cents or listing.price_cents
    total_cents = price_cents + (listing.shipping_cents or 0)
    split = compute_split(total_cents, seller)
    base = settings.public_base_url
    metadata = {"listing_id": str(listing.id), "seller_handle": seller.handle}
    if buyer_user_id is not None:
        metadata["buyer_user_id"] = str(buyer_user_id)
    session_obj = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": settings.platform_currency,
                "product_data": {"name": listing.title},
                "unit_amount": total_cents,
            },
            "quantity": 1,
        }],
        payment_intent_data={
            "application_fee_amount": split.platform_fee_cents,
            "transfer_data": {"destination": seller.stripe_account_id},
        },
        metadata=metadata,
        success_url=f"{base}/?checkout=success&listing={listing.id}",
        cancel_url=f"{base}/?checkout=cancel&listing={listing.id}",
    )
    return {"id": session_obj.id, "url": session_obj.url, "application_fee": split.as_dict()}


def construct_event(payload: bytes, sig_header: str):
    """Verify + parse a Stripe webhook event."""
    stripe = _stripe()
    if not settings.stripe_webhook_secret:
        raise PaymentsError("STRIPE_WEBHOOK_SECRET is not set.")
    return stripe.Webhook.construct_event(
        payload, sig_header, settings.stripe_webhook_secret
    )

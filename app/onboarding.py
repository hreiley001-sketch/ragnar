"""Seller onboarding checklist — payouts → listing → sale → verification.

Derived from live seller state (no separate checklist table). See
vault/Ragnarips/SellerOnboarding/README.md.
"""
from __future__ import annotations

from typing import Optional

from sqlmodel import Session, func, select

from .models import (
    Listing,
    ListingStatus,
    Order,
    Seller,
    SellerVerificationStatus,
    utcnow,
)

# Ordered steps shown in My Store. `required` must all be done for "complete".
STEPS_SPEC = (
    {
        "id": "create_store",
        "title": "Create your store",
        "blurb": "Claim a handle and open your storefront.",
        "required": True,
        "cta_label": "View storefront",
        "cta_href": None,  # filled with /store/{handle}
    },
    {
        "id": "connect_payouts",
        "title": "Connect payouts",
        "blurb": "Link Stripe so buyers can check out and you get paid.",
        "required": True,
        "cta_label": "Set up payouts",
        "cta_action": "connect_payouts",
    },
    {
        "id": "first_listing",
        "title": "List your first card",
        "blurb": "Structured listing with photo — scan-to-post helps.",
        "required": True,
        "cta_label": "List with AI",
        "cta_action": "open_sell",
    },
    {
        "id": "get_verified",
        "title": "Get verified",
        "blurb": "Verified sellers earn a trust badge and lower fraud score.",
        "required": False,
        "cta_label": "Request verification",
        "cta_action": "request_verification",
    },
    {
        "id": "first_sale",
        "title": "Close your first sale",
        "blurb": "A paid order or recorded sale means the flywheel started.",
        "required": True,
        "cta_label": "View storefront",
        "cta_href": None,
    },
)


def _listing_count(session: Session, seller_id: int) -> int:
    return int(
        session.exec(
            select(func.count()).select_from(Listing).where(Listing.seller_id == seller_id)
        ).one()
        or 0
    )


def _sale_count(session: Session, seller_id: int) -> int:
    orders = int(
        session.exec(
            select(func.count()).select_from(Order).where(Order.seller_id == seller_id)
        ).one()
        or 0
    )
    sold_listings = int(
        session.exec(
            select(func.count()).select_from(Listing).where(
                Listing.seller_id == seller_id,
                Listing.status == ListingStatus.sold.value,
            )
        ).one()
        or 0
    )
    return max(orders, sold_listings)


def step_done(session: Session, seller: Seller, step_id: str) -> bool:
    if step_id == "create_store":
        return seller.id is not None
    if step_id == "connect_payouts":
        return bool(seller.stripe_charges_enabled)
    if step_id == "first_listing":
        return _listing_count(session, seller.id) > 0  # type: ignore[arg-type]
    if step_id == "get_verified":
        return seller.verification_status == SellerVerificationStatus.verified.value
    if step_id == "first_sale":
        return _sale_count(session, seller.id) > 0  # type: ignore[arg-type]
    return False


def step_status(session: Session, seller: Seller, step_id: str) -> str:
    """done | pending | todo"""
    if step_done(session, seller, step_id):
        return "done"
    if step_id == "connect_payouts" and seller.stripe_account_id and not seller.stripe_charges_enabled:
        return "pending"
    if step_id == "get_verified" and seller.verification_status == SellerVerificationStatus.pending.value:
        return "pending"
    return "todo"


def build_checklist(session: Session, seller: Seller) -> dict:
    steps = []
    done_required = 0
    total_required = 0
    for spec in STEPS_SPEC:
        st = step_status(session, seller, spec["id"])
        href = spec.get("cta_href")
        if href is None and spec["id"] in {"create_store", "first_sale"}:
            href = f"/store/{seller.handle}"
        step = {
            "id": spec["id"],
            "title": spec["title"],
            "blurb": spec["blurb"],
            "required": spec["required"],
            "status": st,
            "cta_label": spec.get("cta_label"),
            "cta_action": spec.get("cta_action"),
            "cta_href": href,
        }
        steps.append(step)
        if spec["required"]:
            total_required += 1
            if st == "done":
                done_required += 1

    complete = done_required >= total_required and total_required > 0
    next_step = next((s for s in steps if s["status"] != "done"), None)
    return {
        "handle": seller.handle,
        "display_name": seller.display_name,
        "complete": complete,
        "progress": {
            "done_required": done_required,
            "total_required": total_required,
            "percent": round(100 * done_required / total_required) if total_required else 100,
        },
        "next_step_id": next_step["id"] if next_step else None,
        "verification_status": seller.verification_status,
        "trust_status": seller.trust_status,
        "stripe_connected": bool(seller.stripe_account_id),
        "stripe_charges_enabled": bool(seller.stripe_charges_enabled),
        "listing_count": _listing_count(session, seller.id),  # type: ignore[arg-type]
        "sale_count": _sale_count(session, seller.id),  # type: ignore[arg-type]
        "onboarding_completed_at": (
            seller.onboarding_completed_at.isoformat()
            if getattr(seller, "onboarding_completed_at", None)
            else None
        ),
        "steps": steps,
    }


def maybe_mark_complete(session: Session, seller: Seller) -> bool:
    """Stamp onboarding_completed_at once when required steps are done. Returns True if newly completed."""
    checklist = build_checklist(session, seller)
    if not checklist["complete"]:
        return False
    if getattr(seller, "onboarding_completed_at", None):
        return False
    seller.onboarding_completed_at = utcnow()
    session.add(seller)
    return True


def request_verification(
    session: Session,
    seller: Seller,
    *,
    actor_user_id: Optional[int] = None,
) -> Seller:
    """Seller self-serve: move unverified → pending for ops / future Stripe Identity."""
    from . import trust as trust_svc

    current = seller.verification_status or SellerVerificationStatus.unverified.value
    if current == SellerVerificationStatus.verified.value:
        return seller
    if current == SellerVerificationStatus.pending.value:
        return seller
    trust_svc.set_verification(
        session,
        seller,
        SellerVerificationStatus.pending.value,
        actor_user_id=actor_user_id,
        detail="Seller requested verification via onboarding checklist",
    )
    return seller

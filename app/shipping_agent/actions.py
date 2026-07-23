"""Action tools Dispatch can call — rates, labels, ship, track, profiles."""
from __future__ import annotations

import logging
from typing import Optional

from sqlmodel import Session, select

from ..models import (
    Listing,
    Order,
    OrderStatus,
    Seller,
    SellerShippingProfile,
    ShippingConversation,
    ShippingLabel,
    utcnow,
)
from ..notify import notify, notify_admins, notify_seller
from .. import shipping as ship

logger = logging.getLogger("ragnar.dispatch.actions")


def get_seller_order(
    session: Session,
    order_id: int,
    *,
    seller_id: Optional[int] = None,
    user_id: Optional[int] = None,
    staff: bool = False,
) -> Optional[Order]:
    order = session.get(Order, order_id)
    if not order:
        return None
    if staff:
        return order
    if seller_id and order.seller_id == seller_id:
        return order
    # Allow the authenticated user who owns the seller account.
    if user_id and order.seller_id:
        seller = session.get(Seller, order.seller_id)
        # Seller has no user_id FK historically — match via email when present.
        if seller and seller.email:
            from ..models import User
            user = session.get(User, user_id)
            if user and user.email and user.email.lower() == seller.email.lower():
                return order
    return None


def list_to_ship(
    session: Session,
    *,
    seller_id: Optional[int] = None,
    limit: int = 20,
) -> list[Order]:
    q = select(Order).order_by(Order.created_at.asc()).limit(200)
    if seller_id:
        q = select(Order).where(Order.seller_id == seller_id).order_by(Order.created_at.asc()).limit(200)
    rows = session.exec(q).all()
    out = [
        o for o in rows
        if o.status in (OrderStatus.paid.value, OrderStatus.pending.value)
    ]
    return out[:limit]


def order_summary(session: Session, order: Order) -> dict:
    seller = session.get(Seller, order.seller_id) if order.seller_id else None
    listing = session.get(Listing, order.listing_id) if order.listing_id else None
    return {
        "id": order.id,
        "title": order.title,
        "status": order.status,
        "price": round(order.price_cents / 100, 2),
        "shipping": round((order.shipping_cents or 0) / 100, 2),
        "total": round((order.price_cents + (order.shipping_cents or 0)) / 100, 2),
        "tracking_number": order.tracking_number,
        "carrier": order.carrier,
        "tracking_url": ship.tracking_url(order.carrier, order.tracking_number),
        "seller_handle": seller.handle if seller else None,
        "is_graded": bool(listing.is_graded) if listing else None,
        "buyer_name": order.buyer_name,
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }


def get_profile(session: Session, seller_id: int) -> Optional[SellerShippingProfile]:
    return session.exec(
        select(SellerShippingProfile).where(SellerShippingProfile.seller_id == seller_id)
    ).first()


def upsert_ship_from(
    session: Session,
    *,
    seller_id: int,
    address: dict,
    prefer: str = "balanced",
) -> SellerShippingProfile:
    row = get_profile(session, seller_id)
    if not row:
        row = SellerShippingProfile(seller_id=seller_id)
    row.name = (address.get("name") or row.name or "Seller")[:120]
    row.street1 = (address.get("street1") or "")[:120]
    row.city = (address.get("city") or "")[:80]
    row.state = (address.get("state") or "")[:40]
    row.zip = str(address.get("zip") or "")[:20]
    row.country = (address.get("country") or "US")[:2].upper()
    if address.get("phone"):
        row.phone = str(address["phone"])[:40]
    if prefer in ("cheapest", "fastest", "balanced"):
        row.prefer = prefer
    row.updated_at = utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def profile_as_address(profile: SellerShippingProfile | None) -> dict | None:
    if not profile or not profile.street1:
        return None
    return {
        "name": profile.name or "Seller",
        "street1": profile.street1,
        "city": profile.city,
        "state": profile.state,
        "zip": profile.zip,
        "country": profile.country or "US",
        "phone": profile.phone,
    }


def default_ship_to(order: Order, override: dict | None = None) -> dict:
    if override and override.get("street1"):
        return {
            "name": override.get("name") or order.buyer_name or "Buyer",
            "street1": override["street1"],
            "city": override.get("city") or "",
            "state": override.get("state") or "",
            "zip": override.get("zip") or "",
            "country": override.get("country") or "US",
            "email": order.buyer_email,
        }
    # Checkout doesn't yet persist full ship-to on Order — use a safe demo default
    # so rate shopping still works; sellers can override via chat.
    return {
        "name": order.buyer_name or "Buyer",
        "street1": "1 Market Street",
        "city": "San Francisco",
        "state": "CA",
        "zip": "94105",
        "country": "US",
        "email": order.buyer_email,
        "note": "Placeholder ship-to — paste the buyer's address to override.",
    }


def default_ship_from(session: Session, order: Order, conv: ShippingConversation) -> dict:
    ctx = conv.context or {}
    if ctx.get("ship_from") and ctx["ship_from"].get("street1"):
        return ctx["ship_from"]
    if order.seller_id:
        profile = get_profile(session, order.seller_id)
        addr = profile_as_address(profile)
        if addr:
            return addr
    return {
        "name": "RAGNAR Seller",
        "street1": "100 Warehouse Way",
        "city": "Austin",
        "state": "TX",
        "zip": "78701",
        "country": "US",
        "note": "Placeholder ship-from — save your address with Dispatch.",
    }


def quote_for_order(
    session: Session,
    order: Order,
    conv: ShippingConversation,
    *,
    prefer: str = "balanced",
    is_graded: bool | None = None,
) -> dict:
    listing = session.get(Listing, order.listing_id) if order.listing_id else None
    graded = (
        is_graded if is_graded is not None
        else (bool(listing.is_graded) if listing else False)
    )
    pack = ship.recommend_packaging(
        is_graded=graded,
        quantity=1,
        value_cents=order.price_cents,
    )
    address_from = default_ship_from(session, order, conv)
    address_to = default_ship_to(order, (conv.context or {}).get("ship_to"))
    rates = ship.get_rates(address_from, address_to, pack["parcel"])
    best = ship.recommend_rate(rates, prefer=prefer, value_cents=order.price_cents)
    insurance = pack["recommended_insurance_cents"]
    return {
        "order": order_summary(session, order),
        "packaging": pack,
        "address_from": address_from,
        "address_to": address_to,
        "rates": rates[:8],
        "recommended": best,
        "insurance_cents": insurance,
        "shippo_live": ship.is_configured(),
    }


def purchase_label(
    session: Session,
    order: Order,
    conv: ShippingConversation,
    *,
    prefer: str = "balanced",
    rate: dict | None = None,
) -> dict:
    quote = quote_for_order(session, order, conv, prefer=prefer)
    chosen = rate or quote.get("recommended") or {}
    label = ship.create_label(
        rate_object_id=chosen.get("object_id"),
        carrier=chosen.get("provider"),
        service=chosen.get("service"),
        amount=str(chosen.get("amount") or ""),
        address_from=quote["address_from"],
        address_to=quote["address_to"],
        parcel=quote["packaging"]["parcel"],
    )
    amount_cents = 0
    try:
        amount_cents = int(round(float(label.get("amount") or 0) * 100))
    except (TypeError, ValueError):
        amount_cents = 0
    row = ShippingLabel(
        order_id=order.id,
        seller_id=order.seller_id,
        conversation_id=conv.id,
        label_id=label["label_id"],
        carrier=label.get("carrier"),
        service=label.get("service"),
        tracking_number=label.get("tracking_number"),
        amount_cents=amount_cents,
        label_url=label.get("label_url"),
        source=label.get("source") or "mock",
        status="purchased",
        package_key=quote["packaging"].get("package_key"),
        insurance_cents=quote.get("insurance_cents") or 0,
        address_from=quote["address_from"],
        address_to=quote["address_to"],
        meta={"rate": chosen, "note": label.get("note")},
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    label["shipping_label_db_id"] = row.id
    label["packaging"] = quote["packaging"]
    label["insurance_cents"] = row.insurance_cents
    return label


def mark_shipped(
    session: Session,
    order: Order,
    *,
    tracking_number: str,
    carrier: str | None = None,
) -> dict:
    order.tracking_number = tracking_number.strip()
    order.carrier = (carrier or ship.detect_carrier(tracking_number) or "").strip() or None
    order.status = OrderStatus.shipped.value
    order.updated_at = utcnow()
    session.add(order)
    session.commit()
    session.refresh(order)
    if order.buyer_user_id:
        notify(
            session, order.buyer_user_id, "order_shipped",
            f"Your order shipped — {order.title}",
            body=f"Tracking: {order.tracking_number}"
                 + (f" ({order.carrier})" if order.carrier else ""),
            link="/account#orders",
        )
    return order_summary(session, order)


def flag_human_review(
    session: Session,
    conv: ShippingConversation,
    *,
    reason: str,
) -> None:
    conv.status = (
        conv.status
        if conv.status == "escalated"
        else "pending_review"
    )
    ctx = dict(conv.context or {})
    ctx["review_reason"] = reason[:500]
    conv.context = ctx
    conv.updated_at = utcnow()
    session.add(conv)
    session.commit()
    notify_admins(
        session, "shipping_review",
        f"Dispatch needs review — {conv.public_id}",
        body=reason[:200],
        link="/admin",
    )
    if conv.seller_id:
        seller = session.get(Seller, conv.seller_id)
        notify_seller(
            session, seller, "shipping_review",
            "Dispatch flagged a shipping case",
            body=reason[:200],
            link="/shipping",
        )

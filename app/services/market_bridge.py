"""Market bridge — dual-write storefront commerce → Birdman memory + n8n.

Never raises into the hot path. SQLModel stays source of truth until cutover;
Supabase + jobs get a best-effort mirror so the organism stays warm.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from app.core import supabase_rest
from app.core.cache import invalidate
from app.core.jobs import enqueue_job
from app.models import Listing, Order, User
from app.services.user_service import actor_id

logger = logging.getLogger("ragnar.services.market_bridge")


def mirror_listing_created(
    listing: Listing,
    *,
    user: Optional[User] = None,
    seller_user_id: Optional[str] = None,
) -> None:
    """Best-effort: card + listing rows in Supabase + listing_created job."""
    try:
        owner = seller_user_id
        if not owner and user is not None:
            owner = actor_id(user)
        if not owner:
            owner = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ragnar:seller:{listing.seller_id}"))

        card_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ragnar:card:{listing.id}"))
        listing_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ragnar:listing:{listing.id}"))
        price = round((listing.price_cents or 0) / 100, 2)

        card_row: dict[str, Any] = {
            "id": card_id,
            "owner_id": owner,
            "name": listing.title,
            "set_name": listing.set_name,
            "year": listing.year,
            "grade": str(listing.grade) if listing.grade is not None else (
                listing.condition or None
            ),
            "metadata": {
                "legacy_listing_id": listing.id,
                "category": listing.category,
                "card_number": listing.card_number,
                "player_or_character": listing.player_or_character,
                "is_graded": listing.is_graded,
                "grading_company": listing.grading_company,
                "image_url": listing.image_url,
                "seller_name": listing.seller_name,
            },
        }
        supabase_rest.insert("cards", card_row)

        list_row: dict[str, Any] = {
            "id": listing_uuid,
            "card_id": card_id,
            "seller_id": owner,
            "price": price,
            "status": "active" if (listing.status or "active") == "active" else listing.status,
        }
        saved = supabase_rest.insert("listings", list_row)

        enqueue_job(
            "listing_created",
            user_id=owner,
            extra={
                "listing_id": listing_uuid,
                "legacy_listing_id": listing.id,
                "card_id": card_id,
                "price": price,
                "title": listing.title,
                "persisted": saved is not None,
            },
        )
        enqueue_job(
            "broadcast_event",
            user_id=owner,
            extra={
                "channel": "marketplace",
                "event_type": "listing_created",
                "data": {
                    "legacy_listing_id": listing.id,
                    "listing_id": listing_uuid,
                    "title": listing.title,
                    "price": price,
                },
            },
        )
        invalidate("market:listings:active", "market:feed")
    except Exception as exc:  # noqa: BLE001
        logger.warning("mirror_listing_created skipped: %s", exc)


def mirror_order_paid(
    order: Order,
    listing: Listing,
    *,
    buyer: Optional[User] = None,
) -> None:
    """Best-effort: Birdman order + market jobs after Stripe paid."""
    try:
        buyer_id = actor_id(buyer) if buyer else str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"ragnar:buyer:{order.buyer_email or order.id}")
        )
        listing_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ragnar:listing:{listing.id}"))
        order_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ragnar:order:{order.id}"))
        total = round(((order.price_cents or 0) + (order.shipping_cents or 0)) / 100, 2)

        seller_id = str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"ragnar:seller:{listing.seller_id}")
        )

        row: dict[str, Any] = {
            "id": order_uuid,
            "buyer_id": buyer_id,
            "listing_id": listing_uuid,
            "status": "paid",
            "total": total,
        }
        saved = supabase_rest.insert("orders", row)
        supabase_rest.patch("listings", {"id": f"eq.{listing_uuid}"}, {"status": "sold"})

        enqueue_job(
            "order_placed",
            user_id=buyer_id,
            extra={
                "order_id": order_uuid,
                "legacy_order_id": order.id,
                "listing_id": listing_uuid,
                "legacy_listing_id": listing.id,
                "seller_id": seller_id,
                "total": total,
                "persisted": saved is not None,
            },
        )
        enqueue_job(
            "buyer_notification",
            user_id=buyer_id,
            extra={"order_id": order_uuid, "message": f"Order paid — {listing.title}"},
        )
        enqueue_job(
            "seller_notification",
            user_id=seller_id,
            extra={"order_id": order_uuid, "message": f"You sold — {listing.title}"},
        )
        invalidate("market:listings:active", "market:feed")
    except Exception as exc:  # noqa: BLE001
        logger.warning("mirror_order_paid skipped: %s", exc)


def mirror_order_status(
    order: Order,
    *,
    status: str,
    actor: Optional[User] = None,
) -> None:
    """Best-effort status change → n8n + optional Supabase patch."""
    try:
        order_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"ragnar:order:{order.id}"))
        actor_uid = actor_id(actor) if actor else None
        mapped = {
            "paid": "paid",
            "shipped": "shipped",
            "delivered": "completed",
            "completed": "completed",
            "cancelled": "cancelled",
            "disputed": "cancelled",
        }.get(status, status)
        supabase_rest.patch("orders", {"id": f"eq.{order_uuid}"}, {"status": mapped})
        enqueue_job(
            "order_status_changed",
            user_id=actor_uid,
            extra={
                "order_id": order_uuid,
                "legacy_order_id": order.id,
                "status": mapped,
                "legacy_status": status,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("mirror_order_status skipped: %s", exc)

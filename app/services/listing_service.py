"""Listing service — create/search listings + Redis cache + n8n jobs."""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.core import supabase_rest
from app.core.cache import cached_json, invalidate
from app.core.config import settings
from app.core.jobs import enqueue_job
from app.models.marketplace import ListingCreate, ListingPage, ListingRead
from app.utils.exceptions import NotFoundError, ValidationAppError


def create_listing(seller_id: str, body: ListingCreate) -> ListingRead:
    row: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "card_id": str(body.card_id),
        "seller_id": seller_id,
        "price": float(body.price),
        "status": body.status,
    }
    saved = supabase_rest.insert("listings", row)
    persisted = saved is not None
    data = saved or row

    enqueue_job(
        "listing_created",
        user_id=seller_id,
        extra={
            "listing_id": str(data["id"]),
            "card_id": str(body.card_id),
            "price": float(body.price),
        },
    )
    enqueue_job(
        "broadcast_event",
        user_id=seller_id,
        extra={
            "channel": "marketplace",
            "event_type": "listing_created",
            "data": {"listing_id": str(data["id"]), "price": float(body.price)},
        },
    )
    invalidate("market:listings:active", "market:feed")
    return _to_read(data, persisted=persisted)


def search_active_listings(*, limit: int = 48) -> ListingPage:
    def load() -> dict[str, Any]:
        rows = supabase_rest.select(
            "listings",
            filters={"status": "eq.active"},
            order="created_at.desc",
            limit=limit,
        )
        items = [_to_read(r, persisted=True).model_dump(mode="json") for r in rows]
        return {"items": items, "total": len(items)}

    data = cached_json(
        "market:listings:active",
        ttl_seconds=settings.cache_ttl_listings_seconds,
        loader=load,
    )
    items = [ListingRead.model_validate(i) for i in data.get("items", [])]
    return ListingPage(
        items=items,
        total=int(data.get("total") or 0),
        cached=bool(settings.redis_url),
    )


def update_listing_status(listing_id: str, seller_id: str, status: str) -> ListingRead:
    if status not in {"active", "sold", "cancelled"}:
        raise ValidationAppError("invalid listing status")
    patched = supabase_rest.patch(
        "listings",
        {"id": f"eq.{listing_id}", "seller_id": f"eq.{seller_id}"},
        {"status": status},
    )
    if not patched and supabase_rest.available():
        raise NotFoundError("listing not found")
    data = patched or {
        "id": listing_id,
        "card_id": "00000000-0000-0000-0000-000000000000",
        "seller_id": seller_id,
        "price": 0,
        "status": status,
    }
    invalidate("market:listings:active", "market:feed")
    return _to_read(data, persisted=patched is not None)


def _to_read(data: dict[str, Any], *, persisted: bool) -> ListingRead:
    return ListingRead(
        id=UUID(str(data["id"])),
        card_id=UUID(str(data["card_id"])),
        seller_id=UUID(str(data["seller_id"])),
        price=Decimal(str(data["price"])),
        status=data.get("status") or "active",
        created_at=data.get("created_at"),
        updated_at=data.get("updated_at"),
        persisted=persisted,
    )

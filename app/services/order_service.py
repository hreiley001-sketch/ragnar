"""Order service — place/update orders + notification jobs."""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.core import supabase_rest
from app.core.cache import invalidate
from app.core.jobs import enqueue_job
from app.models.marketplace import OrderCreate, OrderRead, OrderStatusUpdate
from app.utils.exceptions import NotFoundError, ValidationAppError


def place_order(buyer_id: str, body: OrderCreate) -> OrderRead:
    listings = supabase_rest.select(
        "listings",
        filters={"id": f"eq.{body.listing_id}", "status": "eq.active"},
        limit=1,
    )
    listing = listings[0] if listings else None
    total = float(listing["price"]) if listing else 0.0
    if listing is None and supabase_rest.available():
        raise NotFoundError("active listing not found")

    row: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "buyer_id": buyer_id,
        "listing_id": str(body.listing_id),
        "status": "pending",
        "total": total,
    }
    saved = supabase_rest.insert("orders", row)
    persisted = saved is not None
    data = saved or row

    if listing:
        supabase_rest.patch(
            "listings",
            {"id": f"eq.{body.listing_id}"},
            {"status": "sold"},
        )

    enqueue_job(
        "order_placed",
        user_id=buyer_id,
        extra={
            "order_id": str(data["id"]),
            "listing_id": str(body.listing_id),
            "seller_id": listing.get("seller_id") if listing else None,
            "total": total,
        },
    )
    enqueue_job(
        "buyer_notification",
        user_id=buyer_id,
        extra={"order_id": str(data["id"]), "message": "Order placed"},
    )
    if listing and listing.get("seller_id"):
        enqueue_job(
            "seller_notification",
            user_id=str(listing["seller_id"]),
            extra={"order_id": str(data["id"]), "message": "You sold a listing"},
        )
    invalidate("market:listings:active", "market:feed")
    return _to_read(data, persisted=persisted)


def update_order_status(order_id: str, body: OrderStatusUpdate, *, actor_id: str) -> OrderRead:
    patched = supabase_rest.patch(
        "orders",
        {"id": f"eq.{order_id}"},
        {"status": body.status},
    )
    if not patched and supabase_rest.available():
        raise NotFoundError("order not found")
    data = patched or {
        "id": order_id,
        "buyer_id": actor_id,
        "listing_id": "00000000-0000-0000-0000-000000000000",
        "status": body.status,
        "total": 0,
    }
    enqueue_job(
        "order_status_changed",
        user_id=actor_id,
        extra={"order_id": order_id, "status": body.status},
    )
    return _to_read(data, persisted=patched is not None)


def list_orders(buyer_id: str, *, limit: int = 50) -> list[OrderRead]:
    rows = supabase_rest.select(
        "orders",
        filters={"buyer_id": f"eq.{buyer_id}"},
        order="created_at.desc",
        limit=limit,
    )
    return [_to_read(r, persisted=True) for r in rows]


def _to_read(data: dict[str, Any], *, persisted: bool) -> OrderRead:
    return OrderRead(
        id=UUID(str(data["id"])),
        buyer_id=UUID(str(data["buyer_id"])),
        listing_id=UUID(str(data["listing_id"])),
        status=data.get("status") or "pending",
        total=Decimal(str(data.get("total") or 0)),
        created_at=data.get("created_at"),
        persisted=persisted,
    )

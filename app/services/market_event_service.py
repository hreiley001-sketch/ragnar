"""Market event service — live marketplace feed."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core import supabase_rest
from app.core.cache import cached_json
from app.core.config import settings
from app.models.marketplace import MarketEventPage, MarketEventRead


def list_feed(*, limit: int = 40) -> MarketEventPage:
    def load() -> dict[str, Any]:
        rows = supabase_rest.select(
            "market_events",
            order="created_at.desc",
            limit=limit,
        )
        items = [
            {
                "id": str(r["id"]),
                "type": r["type"],
                "user_id": str(r["user_id"]) if r.get("user_id") else None,
                "data": r.get("data") or {},
                "created_at": r.get("created_at"),
            }
            for r in rows
        ]
        return {"items": items, "total": len(items)}

    data = cached_json(
        "market:feed",
        ttl_seconds=min(15, settings.cache_ttl_listings_seconds),
        loader=load,
    )
    items = []
    for raw in data.get("items", []):
        items.append(
            MarketEventRead(
                id=UUID(str(raw["id"])),
                type=raw["type"],
                user_id=UUID(str(raw["user_id"])) if raw.get("user_id") else None,
                data=raw.get("data") or {},
                created_at=raw.get("created_at"),
            )
        )
    return MarketEventPage(
        items=items,
        total=int(data.get("total") or 0),
        cached=bool(settings.redis_url),
    )

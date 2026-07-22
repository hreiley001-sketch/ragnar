"""Card service — create/list cards + enqueue enrichment."""
from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

from app.core import supabase_rest
from app.core.cache import invalidate
from app.core.jobs import enqueue_job
from app.models.marketplace import CardCreate, CardRead


def create_card(owner_id: str, body: CardCreate) -> CardRead:
    row: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "owner_id": owner_id,
        "name": body.name,
        "set_name": body.set_name,
        "year": body.year,
        "grade": body.grade,
        "metadata": body.metadata or {},
    }
    saved = supabase_rest.insert("cards", row)
    persisted = saved is not None
    data = saved or row
    enqueue_job(
        "enrich_content",
        user_id=owner_id,
        content_id=str(data["id"]),
        extra={"entity": "card", "name": body.name},
    )
    invalidate("market:listings:active")
    return CardRead(
        id=UUID(str(data["id"])),
        owner_id=UUID(str(data["owner_id"])),
        name=data["name"],
        set_name=data.get("set_name"),
        year=data.get("year"),
        grade=data.get("grade"),
        metadata=data.get("metadata") or {},
        created_at=data.get("created_at"),
        persisted=persisted,
    )


def list_cards(owner_id: str | None = None, *, limit: int = 50) -> list[CardRead]:
    filters = {"owner_id": f"eq.{owner_id}"} if owner_id else None
    rows = supabase_rest.select("cards", filters=filters, order="created_at.desc", limit=limit)
    return [
        CardRead(
            id=UUID(str(r["id"])),
            owner_id=UUID(str(r["owner_id"])),
            name=r["name"],
            set_name=r.get("set_name"),
            year=r.get("year"),
            grade=r.get("grade"),
            metadata=r.get("metadata") or {},
            created_at=r.get("created_at"),
            persisted=True,
        )
        for r in rows
    ]

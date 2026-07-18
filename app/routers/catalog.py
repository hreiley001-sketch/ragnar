"""Free card-catalog lookups (Scryfall + Pokémon TCG) for autofill/verify."""
from __future__ import annotations

from fastapi import APIRouter, Query

from .. import catalog
from ..models import Category

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


@router.get("/search")
def catalog_search(
    q: str = Query(..., min_length=1, description="Card name"),
    category: Category | None = Query(None),
    limit: int = Query(8, ge=1, le=25),
) -> dict:
    items = catalog.search(q, category.value if category else None, limit=limit)
    return {"items": items, "count": len(items), "supported": list(catalog.providers().keys())}

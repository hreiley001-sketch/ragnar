"""Live market pricing lookups (TCG API)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from ..models import Category
from ..pricing import is_configured, market_price
from ..schemas import MarketPrice

router = APIRouter(prefix="/api/pricing", tags=["pricing"])


@router.get("/search", response_model=MarketPrice)
def pricing_search(
    q: str = Query(..., min_length=1, description="Card name / query"),
    category: Category | None = Query(None, description="Maps to the TCG game"),
    game: str | None = Query(None, description="Explicit TCG game slug override"),
) -> MarketPrice:
    if not is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live pricing not configured. Set TCG_API_KEY to enable.",
        )
    mp = market_price(q, category=category.value if category else None, game=game)
    if not mp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No market price found for that query/game.",
        )
    return MarketPrice(**mp)

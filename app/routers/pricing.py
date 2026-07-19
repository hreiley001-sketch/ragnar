"""Live market pricing lookups (TCG API) + a blended price suggestion."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from ..comps import build_keyword, external_sold
from ..database import get_session
from ..models import Category
from ..pricing import is_configured, market_price
from ..schemas import MarketPrice
from ..services import match_sales, summarize_sales

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


@router.post("/suggest")
def pricing_suggest(payload: dict, session: Session = Depends(get_session)) -> dict:
    """Suggest a listing price by blending signals — RAGNAR's own sold history
    (no key needed), external comps, and live TCG market price. Returns a
    suggested price + low/high range + the basis, so it works even before any
    pricing key is configured."""
    category = payload.get("category")
    player = payload.get("player_or_character")
    title = payload.get("title")
    set_name = payload.get("set_name")
    card_number = payload.get("card_number")

    # 1) RAGNAR sold history + external comps (median = honest suggestion).
    sales = match_sales(
        session,
        category=category, set_name=set_name, card_number=card_number,
        player_or_character=player,
        is_graded=payload.get("is_graded"),
        grading_company=payload.get("grading_company"),
        grade=payload.get("grade"),
    )
    keyword = build_keyword(
        player_or_character=player, title=title, set_name=set_name,
        card_number=card_number, grading_company=payload.get("grading_company"),
        grade=payload.get("grade"),
    )
    hist = summarize_sales(sales, external_sold(keyword) if keyword else [])

    # 2) Live TCG market price.
    query = " ".join(str(x) for x in [player or title, set_name, card_number] if x).strip()
    mp = market_price(query, category=category) if query else None

    basis: list[str] = []
    candidates: list[float] = []
    if hist.get("count"):
        candidates.append(hist["median"])
        basis.append(f"{hist['count']} sold comp{'s' if hist['count'] != 1 else ''} (median ${hist['median']})")
    if mp and mp.get("market"):
        candidates.append(mp["market"])
        basis.append(f"live market ${mp['market']} ({mp.get('source')})")

    suggested = round(sum(candidates) / len(candidates), 2) if candidates else None
    low = hist.get("low") or (mp.get("low") if mp else None)
    high = hist.get("high") or (mp.get("market") if mp else None)

    return {
        "suggested_price": suggested,
        "low": low,
        "high": high,
        "currency": "USD",
        "basis": basis,
        "comp_count": hist.get("count", 0),
        "market": mp,
        "note": None if candidates else "No comps or market data yet — price by feel; your first sales build the history.",
    }

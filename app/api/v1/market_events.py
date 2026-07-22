"""Market events — live marketplace activity feed."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.models.marketplace import MarketEventPage
from app.services import market_event_service

router = APIRouter(prefix="/market-events", tags=["birdman-market-events"])


@router.get("", response_model=MarketEventPage)
def market_feed(limit: int = Query(40, ge=1, le=100)) -> MarketEventPage:
    return market_event_service.list_feed(limit=limit)

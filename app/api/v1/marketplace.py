"""Marketplace BFF — storefront-shaped browse on the Birdman /api/v1 surface.

Returns the rich SQLModel ListingPage DTO (price, title, images) so the UI can
cut over from `/api/listings` without waiting on thin UUID market tables.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.core.cache import cached_json
from app.core.config import settings
from app.database import get_session
from app.models import Category, Condition, GradingCompany
from app.schemas import ListingPage, SortOption
from app.services import listing_query_service

router = APIRouter(prefix="/marketplace", tags=["birdman-marketplace"])


@router.get("/browse", response_model=ListingPage)
def browse(
    session: Session = Depends(get_session),
    q: Optional[str] = Query(None),
    category: Optional[Category] = Query(None),
    set_name: Optional[str] = Query(None),
    condition: Optional[Condition] = Query(None),
    grading_company: Optional[GradingCompany] = Query(None),
    graded: Optional[bool] = Query(None),
    min_grade: Optional[float] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    founding_only: bool = Query(False),
    featured: bool = Query(False),
    sort: SortOption = Query(SortOption.newest),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
) -> ListingPage:
    cache_key = (
        f"market:browse:q={q or ''}|cat={category}|set={set_name}|"
        f"cond={condition}|gc={grading_company}|g={graded}|mg={min_grade}|"
        f"min={min_price}|max={max_price}|f={founding_only}|feat={featured}|"
        f"sort={sort}|p={page}|ps={page_size}"
    )

    def load() -> dict:
        page_obj = listing_query_service.search_listings_page(
            session,
            q=q,
            category=category,
            set_name=set_name,
            condition=condition,
            grading_company=grading_company,
            graded=graded,
            min_grade=min_grade,
            min_price=min_price,
            max_price=max_price,
            founding_only=founding_only,
            featured=featured,
            sort=sort,
            page=page,
            page_size=page_size,
        )
        return page_obj.model_dump(mode="json")

    data = cached_json(
        cache_key,
        ttl_seconds=settings.cache_ttl_listings_seconds,
        loader=load,
    )
    return ListingPage.model_validate(data)


@router.get("/pulse")
def marketplace_pulse() -> dict:
    """Lightweight RAGNAR storefront health — redis + supabase + hub label."""
    from app.services.realtime_service import organism_pulse

    pulse = organism_pulse()
    return {
        "product": pulse.get("product", "ragnar"),
        "organism": pulse.get("organism", "birdman"),
        "hub": pulse.get("hub", "Maps/RAGNAR"),
        "surface": "marketplace",
        "redis": pulse.get("redis"),
        "supabase": pulse.get("supabase"),
        "api": "/api/v1/marketplace/browse",
    }

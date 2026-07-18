"""Reference data + fee quotes that power the storefront's dropdowns and math."""
from __future__ import annotations

from fastapi import APIRouter, Query

from ..ai import is_configured as ai_configured
from ..comps import is_configured as comps_configured
from ..config import settings
from ..fees import fee_config, quote
from ..models import Category, Condition, GradingCompany
from ..payments import status as payments_status
from ..pricing import is_configured as pricing_configured
from ..recognition import active_provider
from ..schemas import SortOption

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/meta")
def meta() -> dict:
    """Everything the UI needs to render structured listing controls."""
    return {
        "app": {
            "name": settings.app_name,
            "version": settings.version,
            "tagline": settings.tagline,
        },
        "categories": [c.value for c in Category],
        "conditions": [c.value for c in Condition],
        "grading_companies": [g.value for g in GradingCompany],
        "sort_options": [s.value for s in SortOption],
        "fees": fee_config(),
        "payments": payments_status(),
        "integrations": {
            "recognition": active_provider(),
            "live_pricing": pricing_configured(),
            "external_comps": comps_configured(),
            "ai": ai_configured(),
            "catalog": True,
            "psa": bool(settings.psa_access_token),
        },
    }


@router.get("/fees/quote")
def fees_quote(
    price: float = Query(..., gt=0, le=1_000_000, description="Sale price in dollars"),
    founding: bool = Query(False, description="Seller is a Founding Seller"),
    founding_intro: bool = Query(
        False, description="Within the Founding intro (0% platform) window"
    ),
) -> dict:
    return quote(price, is_founding=founding, founding_intro=founding_intro)

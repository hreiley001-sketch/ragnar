"""Reference data + fee quotes that power the storefront's dropdowns and math."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from .. import site_config
from ..database import get_session

from ..ai import is_configured as ai_configured
from ..comps import is_configured as comps_configured
from ..emailer import discord_configured, email_configured
from ..enrich import firecrawl_configured, google_fonts_configured, list_fonts
from ..media import (
    background_removal_available,
    cloudinary_configured,
    replicate_configured,
)
from ..shipping import is_configured as shipping_configured
from ..video import is_configured as video_configured
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
            "email": email_configured(),
            "discord": discord_configured(),
            "shipping": shipping_configured(),
            "livekit": video_configured(),
            "media_cdn": cloudinary_configured(),
            "background_removal": background_removal_available(),
            "image_enhance": replicate_configured(),
            "web_extract": firecrawl_configured(),
            "fonts": google_fonts_configured(),
            "n8n": bool(settings.n8n_webhook_url),
            "obsidian": bool(settings.obsidian_api_url and settings.obsidian_api_key),
        },
    }


@router.get("/meta/fonts")
async def meta_fonts(limit: int = Query(60, ge=1, le=200)) -> dict:
    """Popular Google Font families for the store typography picker."""
    return await list_fonts(limit=limit)


@router.get("/site-config")
def site_config_public(session: Session = Depends(get_session)) -> dict:
    """Staff-editable site content (announcement, landing copy, links). Public —
    every page hydrates from this."""
    return site_config.get_all(session)


@router.get("/fees/quote")
def fees_quote(
    price: float = Query(..., gt=0, le=1_000_000, description="Sale price in dollars"),
    founding: bool = Query(False, description="Seller is one of the Founding 250 (flat 4% forever)"),
    founding_intro: bool = Query(
        False, description="Deprecated — no intro window; founding status alone sets the rate"
    ),
) -> dict:
    return quote(price, is_founding=founding, founding_intro=founding_intro)

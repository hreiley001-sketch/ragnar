"""Web-enrichment helpers — Firecrawl (scrape a card page -> price JSON) and
Google Fonts (per-store typography picker).

Key-gated: Firecrawl returns an empty result without a key; Google Fonts falls
back to a curated list so the store typography picker always works.
"""
from __future__ import annotations

import logging
import re

import httpx

from .config import settings

logger = logging.getLogger("ragnar.enrich")

_PRICE_RE = re.compile(r"\$\s?([0-9][0-9,]*(?:\.[0-9]{2})?)")

# Curated fallback so the typography picker works before a Google Fonts key is set.
_FALLBACK_FONTS = [
    {"family": "Inter", "category": "sans-serif"},
    {"family": "Roboto", "category": "sans-serif"},
    {"family": "Montserrat", "category": "sans-serif"},
    {"family": "Poppins", "category": "sans-serif"},
    {"family": "Oswald", "category": "sans-serif"},
    {"family": "Bebas Neue", "category": "display"},
    {"family": "Anton", "category": "display"},
    {"family": "Cinzel", "category": "serif"},
    {"family": "Playfair Display", "category": "serif"},
    {"family": "Merriweather", "category": "serif"},
    {"family": "Lora", "category": "serif"},
    {"family": "Rubik", "category": "sans-serif"},
    {"family": "Space Grotesk", "category": "sans-serif"},
    {"family": "Work Sans", "category": "sans-serif"},
    {"family": "Nunito", "category": "sans-serif"},
    {"family": "Raleway", "category": "sans-serif"},
    {"family": "Teko", "category": "sans-serif"},
    {"family": "Orbitron", "category": "sans-serif"},
    {"family": "Cormorant Garamond", "category": "serif"},
    {"family": "JetBrains Mono", "category": "monospace"},
]


def firecrawl_configured() -> bool:
    return bool(settings.firecrawl_api_key)


def google_fonts_configured() -> bool:
    return bool(settings.google_fonts_api_key)


async def scrape_price(url: str) -> dict:
    """Scrape ``url`` via Firecrawl and extract dollar prices from the page.

    Returns ``{configured, ok, high, low, avg, count, currency, title, source}``.
    Prices are parsed from the cleaned markdown — pragmatic and provider-agnostic.
    """
    out = {
        "configured": firecrawl_configured(),
        "ok": False,
        "high": None,
        "low": None,
        "avg": None,
        "count": 0,
        "currency": "USD",
        "title": None,
        "source": url,
    }
    if not firecrawl_configured() or not url:
        return out
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                f"{settings.firecrawl_base}/v1/scrape",
                headers={"Authorization": f"Bearer {settings.firecrawl_api_key}"},
                json={"url": url, "formats": ["markdown"], "onlyMainContent": True},
            )
        if resp.status_code >= 400:
            logger.warning("Firecrawl failed %s: %s", resp.status_code, resp.text[:200])
            return out
        data = (resp.json() or {}).get("data") or {}
        markdown = data.get("markdown") or ""
        out["title"] = (data.get("metadata") or {}).get("title")
        prices: list[float] = []
        for m in _PRICE_RE.findall(markdown):
            try:
                v = float(m.replace(",", ""))
            except ValueError:
                continue
            # Ignore noise: sub-$1 and absurd values.
            if 1.0 <= v <= 1_000_000.0:
                prices.append(round(v, 2))
        if prices:
            out.update(
                ok=True,
                high=max(prices),
                low=min(prices),
                avg=round(sum(prices) / len(prices), 2),
                count=len(prices),
            )
        else:
            out["ok"] = True  # scrape worked, just no prices found
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("Firecrawl error: %s", exc)
        return out


async def list_fonts(limit: int = 60) -> dict:
    """Popular Google Font families for the store typography picker.

    Uses the Google Fonts API when a key is set; otherwise a curated fallback.
    """
    if not google_fonts_configured():
        return {"source": "fallback", "items": _FALLBACK_FONTS[:limit]}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                "https://www.googleapis.com/webfonts/v1/webfonts",
                params={"key": settings.google_fonts_api_key, "sort": "popularity"},
            )
        if resp.status_code >= 400:
            logger.warning("Google Fonts failed %s: %s", resp.status_code, resp.text[:200])
            return {"source": "fallback", "items": _FALLBACK_FONTS[:limit]}
        items = (resp.json() or {}).get("items") or []
        fonts = [{"family": it.get("family"), "category": it.get("category")}
                 for it in items[:limit] if it.get("family")]
        return {"source": "google", "items": fonts or _FALLBACK_FONTS[:limit]}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Google Fonts error: %s", exc)
        return {"source": "fallback", "items": _FALLBACK_FONTS[:limit]}

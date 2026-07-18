"""SEO / keyword research tools for the admin hub.

Pluggable providers (all key-gated, graceful when unconfigured):
- Serper (https://serper.dev) — fast, cheap Google SERP + related searches / PAA.
- DataForSEO (https://dataforseo.com) — keyword search volumes & ideas.

Returns keyword ideas the admin can use to shape landing copy, store names, and
content. Nothing here is customer-facing.
"""
from __future__ import annotations

import base64
import logging

import httpx

from .config import settings

logger = logging.getLogger("ragnar.seo")


def providers_status() -> dict:
    return {
        "serper": bool(settings.serper_api_key),
        "dataforseo": bool(settings.dataforseo_login and settings.dataforseo_password),
    }


def is_configured() -> bool:
    s = providers_status()
    return s["serper"] or s["dataforseo"]


def _serper(query: str) -> dict | None:
    if not settings.serper_api_key:
        return None
    try:
        with httpx.Client(timeout=25.0) as client:
            resp = client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"},
                json={"q": query, "gl": "us", "hl": "en"},
            )
        if resp.status_code >= 400:
            logger.warning("Serper failed %s: %s", resp.status_code, resp.text[:200])
            return None
        data = resp.json()
        related = [r.get("query") for r in (data.get("relatedSearches") or []) if r.get("query")]
        paa = [q.get("question") for q in (data.get("peopleAlsoAsk") or []) if q.get("question")]
        top = [
            {"title": o.get("title"), "link": o.get("link")}
            for o in (data.get("organic") or [])[:5]
        ]
        return {
            "provider": "serper",
            "related_keywords": related,
            "people_also_ask": paa,
            "top_results": top,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Serper error: %s", exc)
        return None


def _dataforseo_volume(keywords: list[str]) -> dict | None:
    if not (settings.dataforseo_login and settings.dataforseo_password):
        return None
    auth = base64.b64encode(
        f"{settings.dataforseo_login}:{settings.dataforseo_password}".encode()
    ).decode()
    try:
        with httpx.Client(timeout=40.0) as client:
            resp = client.post(
                "https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live",
                headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
                json=[{"keywords": keywords[:20], "location_code": 2840, "language_code": "en"}],
            )
        if resp.status_code >= 400:
            logger.warning("DataForSEO failed %s: %s", resp.status_code, resp.text[:200])
            return None
        payload = resp.json()
        items = (((payload.get("tasks") or [{}])[0]).get("result")) or []
        volumes = [
            {
                "keyword": it.get("keyword"),
                "search_volume": it.get("search_volume"),
                "competition": it.get("competition"),
                "cpc": it.get("cpc"),
            }
            for it in items
        ]
        return {"provider": "dataforseo", "volumes": volumes}
    except Exception as exc:  # noqa: BLE001
        logger.warning("DataForSEO error: %s", exc)
        return None


def keyword_research(query: str) -> dict:
    """Combine whatever providers are configured into one keyword report."""
    result: dict = {"query": query, "configured": is_configured(), "providers": providers_status()}
    serper = _serper(query)
    if serper:
        result.update(serper)
    # Enrich related keywords with volumes if DataForSEO is available.
    seeds = [query] + (result.get("related_keywords") or [])
    dfs = _dataforseo_volume(seeds)
    if dfs:
        result["volumes"] = dfs["volumes"]
    if not is_configured():
        result["note"] = (
            "No SEO provider configured. Add SERPER_API_KEY (cheap SERP + related "
            "keywords) and/or DATAFORSEO_LOGIN/PASSWORD (search volumes) to enable."
        )
    return result

"""External sold-comps provider (defaults to the SoldComps shape).

GET {COMPS_PROVIDER_URL}?keyword=...   with header  {COMPS_AUTH_HEADER}: <key>
Response: {"items":[{soldPrice,soldCurrency,shippingPrice,endedAt,title,url,...}]}

Key-gated: with no provider URL+key configured, external_sold() returns [] and
the app relies solely on RAGNAR's own sold history. Point COMPS_PROVIDER_URL at
any provider returning that item shape.
"""
from __future__ import annotations

import logging
from datetime import datetime

import httpx

from .config import settings
from .models import utcnow

logger = logging.getLogger("ragnar.comps")


def is_configured() -> bool:
    return bool(settings.comps_provider_url and settings.comps_provider_key)


def build_keyword(
    *,
    player_or_character: str | None = None,
    title: str | None = None,
    set_name: str | None = None,
    card_number: str | None = None,
    grading_company: str | None = None,
    grade: float | None = None,
) -> str:
    parts = [
        player_or_character or title,
        set_name,
        card_number,
    ]
    if grading_company:
        parts.append(grading_company)
        if grade is not None:
            parts.append(str(grade))
    return " ".join(p for p in parts if p).strip()


def _parse_dt(value) -> datetime:
    if not value:
        return utcnow()
    try:
        s = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.replace(tzinfo=None)  # store naive UTC to match the rest of the app
    except (TypeError, ValueError):
        return utcnow()


def external_sold(keyword: str, *, limit: int = 50) -> list[dict]:
    """Fetch external sold listings, normalized to RAGNAR comp dicts."""
    if not is_configured() or not keyword:
        return []
    headers = {settings.comps_auth_header: settings.comps_provider_key}
    params = {"keyword": keyword, "limit": limit}
    try:
        with httpx.Client(timeout=25.0) as client:
            resp = client.get(settings.comps_provider_url, params=params, headers=headers)
        if resp.status_code >= 400:
            logger.warning("Comps provider failed %s: %s", resp.status_code, resp.text[:200])
            return []
        items = (resp.json() or {}).get("items") or []
        comps: list[dict] = []
        for it in items:
            price = it.get("soldPrice") if it.get("soldPrice") is not None else it.get("price")
            try:
                price = round(float(price), 2)
            except (TypeError, ValueError):
                continue
            comps.append({
                "price": price,
                "sold_at": _parse_dt(it.get("endedAt") or it.get("sold_at")),
                "grading_company": None,
                "grade": None,
                "condition": it.get("condition"),
                "source": settings.comps_provider or "external",
                "title": it.get("title"),
                "url": it.get("url"),
            })
        return comps
    except Exception as exc:  # noqa: BLE001
        logger.warning("Comps provider error: %s", exc)
        return []

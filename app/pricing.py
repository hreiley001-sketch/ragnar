"""Live market pricing via TCG API (https://tcgapi.dev).

GET {base}/v1/search?q={query}&game={game}  with header  X-API-Key: <key>
Response: {"data": [{name,set,number,rarity,price,low_price,foil_price,
                     price_change_7d,total_listings}], "pagination": {...}}

Key-gated: with no TCG_API_KEY set, everything here reports "not configured"
and callers simply omit live pricing. Only applies to TCG categories (Pokémon,
MTG, etc.) — sports cards use sold comps instead.
"""
from __future__ import annotations

import logging

from .config import settings
from .http_client import sync_client
from .models import Category

logger = logging.getLogger("ragnar.pricing")

# RAGNAR category -> TCG API game slug. Sports/Other have no TCG price feed.
_CATEGORY_TO_GAME = {
    Category.pokemon.value: "pokemon",
    Category.magic.value: "magic",
    Category.yugioh.value: "yugioh",
    Category.one_piece.value: "onepiece",
    Category.lorcana.value: "lorcana",
}


def is_configured() -> bool:
    return bool(settings.tcg_api_key)


def game_for_category(category: str | None) -> str | None:
    return _CATEGORY_TO_GAME.get(category or "")


def _num(v):
    try:
        return round(float(v), 2) if v is not None else None
    except (TypeError, ValueError):
        return None


def market_price(query: str, category: str | None = None, game: str | None = None) -> dict | None:
    """Look up the best market price for a card. Returns a normalized dict or
    None (not configured / no match / error)."""
    if not is_configured() or not query:
        return None
    game = game or game_for_category(category)
    if not game:
        return None
    try:
        resp = sync_client(timeout=20.0).get(
            f"{settings.tcg_api_base}/v1/search",
            params={"q": query, "game": game},
            headers={"X-API-Key": settings.tcg_api_key},
            timeout=20.0,
        )
        if resp.status_code >= 400:
            logger.warning("TCG API failed %s: %s", resp.status_code, resp.text[:200])
            return None
        data = (resp.json() or {}).get("data") or []
        if not data:
            return None
        top = data[0]
        return {
            "matched_name": top.get("name"),
            "set": top.get("set"),
            "number": top.get("number"),
            "rarity": top.get("rarity"),
            "market": _num(top.get("price")),
            "low": _num(top.get("low_price")),
            "foil": _num(top.get("foil_price")),
            "change_7d": _num(top.get("price_change_7d")),
            "listings": top.get("total_listings"),
            "source": "tcgapi.dev",
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("TCG API error: %s", exc)
        return None

"""Free card-database lookups for autofill + verification.

- Scryfall (Magic: The Gathering) — no key, https://api.scryfall.com
- Pokémon TCG API (Pokémon) — works without a key (key raises limits)

Both return a common shape: {name, set_name, card_number, year, image_url,
rarity, source}. Other categories return [] (extendable: YGOPRODeck, etc.).

These need no credentials, so they work in production immediately.
"""
from __future__ import annotations

import logging

import httpx

from .config import settings
from .models import Category

logger = logging.getLogger("ragnar.catalog")

_HEADERS = {"User-Agent": settings.catalog_user_agent, "Accept": "application/json"}


def providers() -> dict:
    return {
        Category.magic.value: "scryfall",
        Category.pokemon.value: "pokemontcg",
        Category.yugioh.value: "ygoprodeck",
        Category.lorcana.value: "lorcast",
    }


def _year_from_date(date_str) -> int | None:
    try:
        return int(str(date_str)[:4])
    except (TypeError, ValueError):
        return None


def _scryfall(query: str, limit: int) -> list[dict]:
    with httpx.Client(timeout=15.0, headers=_HEADERS) as client:
        resp = client.get(
            "https://api.scryfall.com/cards/search",
            params={"q": query, "order": "released", "unique": "prints"},
        )
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    out = []
    for c in (resp.json().get("data") or [])[:limit]:
        img = None
        if c.get("image_uris"):
            img = c["image_uris"].get("normal") or c["image_uris"].get("small")
        elif c.get("card_faces"):
            faces = c["card_faces"]
            if faces and faces[0].get("image_uris"):
                img = faces[0]["image_uris"].get("normal")
        out.append({
            "name": c.get("name"),
            "set_name": c.get("set_name"),
            "card_number": c.get("collector_number"),
            "year": _year_from_date(c.get("released_at")),
            "rarity": c.get("rarity"),
            "image_url": img,
            "source": "scryfall",
        })
    return out


def _pokemontcg(query: str, limit: int) -> list[dict]:
    headers = dict(_HEADERS)
    if settings.pokemontcg_key:
        headers["X-Api-Key"] = settings.pokemontcg_key
    token = query.strip()
    # Wildcards can't live inside quotes in the pokemontcg query language.
    name_q = f'name:"{token}"' if " " in token else f"name:{token}*"
    with httpx.Client(timeout=15.0, headers=headers) as client:
        resp = client.get(
            "https://api.pokemontcg.io/v2/cards",
            params={"q": name_q, "pageSize": limit, "orderBy": "-set.releaseDate"},
        )
    resp.raise_for_status()
    out = []
    for c in (resp.json().get("data") or [])[:limit]:
        s = c.get("set") or {}
        out.append({
            "name": c.get("name"),
            "set_name": s.get("name"),
            "card_number": c.get("number"),
            "year": _year_from_date(s.get("releaseDate")),
            "rarity": c.get("rarity"),
            "image_url": (c.get("images") or {}).get("large") or (c.get("images") or {}).get("small"),
            "source": "pokemontcg",
        })
    return out


def _ygoprodeck(query: str, limit: int) -> list[dict]:
    """YGOPRODeck — free Yu-Gi-Oh! database, no key (https://ygoprodeck.com/api-guide/)."""
    with httpx.Client(timeout=15.0, headers=_HEADERS) as client:
        resp = client.get(
            "https://db.ygoprodeck.com/api/v7/cardinfo.php",
            params={"fname": query, "num": limit, "offset": 0},
        )
    if resp.status_code == 400:  # their 'no results' shape
        return []
    resp.raise_for_status()
    out = []
    for c in (resp.json().get("data") or [])[:limit]:
        sets = c.get("card_sets") or []
        images = c.get("card_images") or []
        out.append({
            "name": c.get("name"),
            "set_name": sets[0].get("set_name") if sets else None,
            "card_number": sets[0].get("set_code") if sets else None,
            "year": None,
            "rarity": sets[0].get("set_rarity") if sets else None,
            "image_url": images[0].get("image_url") if images else None,
            "source": "ygoprodeck",
        })
    return out


def _lorcast(query: str, limit: int) -> list[dict]:
    """Lorcast — free Disney Lorcana database, no key (https://lorcast.com/docs/api)."""
    with httpx.Client(timeout=15.0, headers=_HEADERS) as client:
        resp = client.get("https://api.lorcast.com/v0/cards/search", params={"q": query})
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    out = []
    for c in (resp.json().get("results") or [])[:limit]:
        imgs = (c.get("image_uris") or {}).get("digital") or {}
        set_info = c.get("set") or {}
        out.append({
            "name": " - ".join(x for x in (c.get("name"), c.get("version")) if x),
            "set_name": set_info.get("name"),
            "card_number": c.get("collector_number"),
            "year": _year_from_date(c.get("released_at")),
            "rarity": c.get("rarity"),
            "image_url": imgs.get("normal") or imgs.get("small"),
            "source": "lorcast",
        })
    return out


def search(query: str, category: str | None = None, limit: int = 8) -> list[dict]:
    """Look up cards by name for the given category. Returns [] on any error so
    the caller degrades gracefully."""
    if not query:
        return []
    prov = providers().get(category or "")
    try:
        if prov == "scryfall":
            return _scryfall(query, limit)
        if prov == "pokemontcg":
            return _pokemontcg(query, limit)
        if prov == "ygoprodeck":
            return _ygoprodeck(query, limit)
        if prov == "lorcast":
            return _lorcast(query, limit)
        # No category given: best-effort sweep of the free providers.
        if not category:
            for fn in (_scryfall, _pokemontcg, _ygoprodeck, _lorcast):
                try:
                    results = fn(query, limit)
                    if results:
                        return results
                except Exception:  # noqa: BLE001
                    continue
    except Exception as exc:  # noqa: BLE001
        logger.warning("Catalog lookup failed (%s): %s", prov, exc)
    return []

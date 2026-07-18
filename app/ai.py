"""AI layer for RAGNAR — the 'smart' parts of the marketplace.

- Natural-language search: "PSA 10 Charizards under $5k" -> structured filters.
- Listing description generation.

Uses OpenAI when OPENAI_API_KEY is set; otherwise a capable rules-based fallback
so the features still work (just less flexibly). Everything degrades gracefully.
"""
from __future__ import annotations

import json
import logging
import re

import httpx

from .config import settings
from .models import Category, GradingCompany

logger = logging.getLogger("ragnar.ai")

_CATEGORY_VALUES = [c.value for c in Category]
_GRADERS = [g.value for g in GradingCompany]


def is_configured() -> bool:
    return bool(settings.openai_api_key)


def _chat(messages: list[dict], *, max_tokens: int = 400, temperature: float = 0.2) -> str | None:
    if not settings.openai_api_key:
        return None
    try:
        with httpx.Client(timeout=40.0) as client:
            resp = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={
                    "model": settings.openai_vision_model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
        if resp.status_code >= 400:
            logger.warning("OpenAI chat failed %s: %s", resp.status_code, resp.text[:200])
            return None
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as exc:  # noqa: BLE001
        logger.warning("OpenAI chat error: %s", exc)
        return None


# --------------------------------------------------------------------------- #
# Natural-language search -> filters
# --------------------------------------------------------------------------- #

_NL_SYSTEM = (
    "You convert a shopper's natural-language request for trading cards into JSON "
    "filters for a marketplace. Keys (all optional): q (string, the card/player name), "
    f"category (one of {_CATEGORY_VALUES}), graded (bool), grading_company (one of {_GRADERS}), "
    "min_grade (1-10), min_price (number, dollars), max_price (number, dollars), "
    "sort (one of newest, price_asc, price_desc, grade_desc). Return ONLY JSON."
)


def _fallback_parse(query: str) -> dict:
    q = query.strip()
    low = q.lower()
    out: dict = {}

    for cat in _CATEGORY_VALUES:
        base = cat.split(" —")[0].lower()
        if base and base in low:
            out["category"] = cat
            break
    if "pokemon" in low or "pokémon" in low:
        out["category"] = Category.pokemon.value

    m = re.search(r"\b(psa|bgs|sgc|cgc|tag)\b", low)
    if m:
        out["grading_company"] = m.group(1).upper()
        out["graded"] = True
    g = re.search(r"\b(?:psa|bgs|sgc|cgc|tag)?\s*(?:grade\s*)?(10|9\.5|9|8|7)\b", low)
    if g and ("psa" in low or "bgs" in low or "sgc" in low or "cgc" in low or "grade" in low or "graded" in low):
        out["min_grade"] = float(g.group(1))
        out["graded"] = True
    if "graded" in low:
        out["graded"] = True
    if "raw" in low or "ungraded" in low:
        out["graded"] = False

    mu = re.search(r"(?:under|below|less than|<)\s*\$?\s*([\d,]+)", low)
    if mu:
        out["max_price"] = float(mu.group(1).replace(",", ""))
    mo = re.search(r"(?:over|above|more than|>)\s*\$?\s*([\d,]+)", low)
    if mo:
        out["min_price"] = float(mo.group(1).replace(",", ""))

    if "cheap" in low or "cheapest" in low:
        out["sort"] = "price_asc"
    elif "expensive" in low or "high end" in low or "grail" in low:
        out["sort"] = "price_desc"

    # Leftover words become the text query.
    stop = {"psa", "bgs", "sgc", "cgc", "tag", "graded", "raw", "ungraded", "under",
            "over", "below", "above", "less", "more", "than", "cheap", "cheapest",
            "expensive", "grade", "cards", "card", "show", "me", "find", "the", "a",
            "with", "and", "for", "grail"}
    words = [w for w in re.findall(r"[a-zA-Z][a-zA-Z'.-]+", q) if w.lower() not in stop
             and w.lower() not in {c.split(" —")[0].lower() for c in _CATEGORY_VALUES}]
    if words:
        out["q"] = " ".join(words)
    return out


def parse_search(query: str) -> dict:
    """Return {filters: {...}, source: 'openai'|'rules'}."""
    content = _chat(
        [{"role": "system", "content": _NL_SYSTEM}, {"role": "user", "content": query}],
        max_tokens=200, temperature=0,
    )
    if content:
        try:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            data = json.loads(match.group(0) if match else content)
            return {"filters": _clean_filters(data), "source": "openai"}
        except Exception:  # noqa: BLE001
            pass
    return {"filters": _clean_filters(_fallback_parse(query)), "source": "rules"}


def _clean_filters(d: dict) -> dict:
    out = {}
    if d.get("q"):
        out["q"] = str(d["q"])[:120]
    if d.get("category") in _CATEGORY_VALUES:
        out["category"] = d["category"]
    if d.get("grading_company") in _GRADERS:
        out["grading_company"] = d["grading_company"]
    if isinstance(d.get("graded"), bool):
        out["graded"] = d["graded"]
    for k in ("min_grade", "min_price", "max_price"):
        try:
            if d.get(k) is not None:
                out[k] = float(d[k])
        except (TypeError, ValueError):
            pass
    if d.get("sort") in {"newest", "price_asc", "price_desc", "grade_desc"}:
        out["sort"] = d["sort"]
    return out


# --------------------------------------------------------------------------- #
# Listing description generation
# --------------------------------------------------------------------------- #


def generate_description(fields: dict) -> dict:
    """Return {description, source}."""
    name = fields.get("title") or fields.get("player_or_character") or "this card"
    parts = [fields.get("year"), fields.get("set_name"), name]
    if fields.get("card_number"):
        parts.append(f"#{fields['card_number']}")
    if fields.get("is_graded") and fields.get("grading_company"):
        parts.append(f"{fields['grading_company']} {fields.get('grade')}")
    elif fields.get("condition"):
        parts.append(str(fields["condition"]))
    descriptor = " ".join(str(p) for p in parts if p)

    content = _chat([
        {"role": "system", "content": "You write concise, honest, appealing 2-3 sentence "
         "marketplace descriptions for trading cards. No hype, no fake claims, no emojis."},
        {"role": "user", "content": f"Write a listing description for: {descriptor}. "
         f"Details: {json.dumps({k: v for k, v in fields.items() if v})}"},
    ], max_tokens=180, temperature=0.7)
    if content:
        return {"description": content.strip(), "source": "openai"}

    # Fallback template.
    graded = fields.get("is_graded") and fields.get("grading_company")
    cond = (f"Professionally graded {fields['grading_company']} {fields.get('grade')}." if graded
            else (f"Condition: {fields['condition']}." if fields.get("condition") else ""))
    text = f"{descriptor}. {cond} Backed by RAGNAR buyer protection and structured, grading-aware listing details.".strip()
    return {"description": re.sub(r"\s+", " ", text), "source": "template"}

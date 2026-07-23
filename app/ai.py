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


_PALETTES = [
    (("gold", "lux", "premium", "elite", "high-end", "luxury", "grail"), "#f0c674", "gold"),
    (("ice", "frost", "cold", "blue", "arctic", "steel", "winter", "chill"), "#6fd6ff", "ice-blue"),
    (("fire", "red", "aggress", "bold", "hot", "inferno", "blood"), "#ff6b5e", "ember-red"),
    (("green", "money", "emerald", "nature", "mint"), "#6fe3b0", "emerald"),
    (("purple", "royal", "mystic", "magic", "cosmic", "galaxy"), "#b18cff", "royal-purple"),
    (("vintage", "retro", "classic", "old-school", "nostalg", "throwback"), "#e0a45e", "vintage-amber"),
    (("pink", "cute", "kawaii", "pastel", "soft"), "#ff9ecb", "pastel-pink"),
]
_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _rules_design(prompt: str, current: dict) -> dict:
    low = prompt.lower()
    color, cname = current.get("accent_color") or "#7fa8c9", "steel"
    for kws, hex_, name in _PALETTES:
        if any(k in low for k in kws):
            color, cname = hex_, name
            break
    focus = None
    for f in ("pokemon", "pokémon", "magic", "mtg", "yugioh", "yu-gi-oh", "one piece",
              "lorcana", "basketball", "baseball", "football", "soccer", "sports",
              "vintage", "graded", "psa", "slabs", "singles"):
        if f in low:
            focus = f
            break
    pretty = cname.replace("-", " ")
    tagline = (f"{pretty.title()} vibes for {focus} collectors." if focus
               else f"A {pretty} store on RAGNAR.")
    bio = ((f"Curated {focus} cards" if focus else "Curated cards")
           + f" with a {pretty} look — grading-aware listings, real sold-price history, "
             "and buyer protection on every sale.")
    # Pick a font that matches the vibe (only when the seller hints at style).
    font = None
    _FONTS = [(("premium", "lux", "elegant", "royal", "regal", "classic", "vintage"), "Cinzel"),
              (("bold", "loud", "hype", "street", "aggressive", "impact"), "Bebas Neue"),
              (("modern", "clean", "minimal", "sleek", "tech"), "Space Grotesk"),
              (("fun", "playful", "cute", "friendly"), "Rubik")]
    for kws, fam in _FONTS:
        if any(k in low for k in kws):
            font = fam
            break
    return {
        "accent_color": color, "tagline": tagline[:140], "bio": bio[:1000],
        "font_family": font,
        "reply": f"Done — I gave your store a {pretty} accent ({color})"
                 + (f" and a {font} font" if font else "") + " with a matching "
                 "tagline and bio. Try “make it darker”, “more premium”, or name what you sell to refine.",
        "source": "rules",
    }


def design_store(prompt: str, current: dict | None = None) -> dict:
    """Turn a plain-English vibe into store customization (accent, tagline, bio)."""
    current = current or {}
    content = _chat([
        {"role": "system", "content": "You are a store-branding designer for a trading-card "
         "marketplace. Given a seller's description and their current store, return ONLY JSON with keys: "
         "accent_color (a #RRGGBB hex that pops on a dark UI), tagline (<=80 chars), "
         "bio (<=240 chars, no emojis), font_family (a real Google Font family name that fits the vibe, "
         "or null to keep current), reply (a short friendly sentence describing what you changed). "
         f"Current store: {json.dumps({k: current.get(k) for k in ('accent_color', 'tagline', 'bio', 'font_family')})}."},
        {"role": "user", "content": prompt},
    ], max_tokens=320, temperature=0.7)
    if content:
        try:
            m = re.search(r"\{.*\}", content, re.DOTALL)
            d = json.loads(m.group(0) if m else content)
            color = d.get("accent_color") if _HEX_RE.match(str(d.get("accent_color", ""))) else (current.get("accent_color") or "#6fd6ff")
            font = d.get("font_family")
            font = str(font)[:80] if font and str(font).lower() not in ("null", "none", "") else None
            return {
                "accent_color": color,
                "tagline": (d.get("tagline") or "")[:140] or None,
                "bio": (d.get("bio") or "")[:1000] or None,
                "font_family": font,
                "reply": d.get("reply") or "Updated your store design.",
                "source": "openai",
            }
        except Exception:  # noqa: BLE001
            pass
    return _rules_design(prompt, current)


# --------------------------------------------------------------------------- #
# RAGNAR Studio — conversational whole-site editor (content + look)
# --------------------------------------------------------------------------- #


def _rules_studio(message: str, current: dict, fields: list[dict]) -> dict:
    """No-OpenAI fallback: still genuinely useful. Maps colour words to the theme
    and routes copy requests to the obvious field."""
    low = message.lower()
    keys = {f["key"] for f in fields}
    updates: dict = {}

    # Colour vibe -> accent (+ a matching deep background for big shifts).
    for kws, hex_, name in _PALETTES:
        if any(k in low for k in kws):
            if "theme_accent" in keys:
                updates["theme_accent"] = hex_
            break

    # Named backgrounds.
    if "theme_bg" in keys:
        if any(w in low for w in ("darker", "black", "midnight", "darkmode", "dark mode", "dark theme")):
            updates["theme_bg"] = "#2a2826"
            if "theme_text" in keys:
                updates["theme_text"] = "#f2f7fc"
        elif any(w in low for w in ("lighter", "brighter", "white", "light mode", "light theme", "wolf fur", "fur grey", "fur gray")):
            updates["theme_bg"] = "#e4e0da"
            if "theme_text" in keys:
                updates["theme_text"] = "#1c1b19"

    # Font requests: "use the font Bebas Neue" / "font: Orbitron".
    m = re.search(r"font\s*(?:to|:|=)?\s*['\"]?([A-Z][A-Za-z ]{2,30})['\"]?", message)
    if m and "theme_font" in keys:
        updates["theme_font"] = m.group(1).strip()

    # Copy routing.
    quoted = re.search(r"['\"]([^'\"]{3,200})['\"]", message)
    said = quoted.group(1).strip() if quoted else None
    if any(w in low for w in ("announce", "banner", "announcement")) and "announcement" in keys:
        updates["announcement"] = said or "Something big is coming to RAGNAR — stay tuned."
    if any(w in low for w in ("headline", "hero", "title", "tagline")) and "hero_headline" in keys and said:
        updates["hero_headline"] = said

    if updates:
        reply = "Done — I applied a few changes. Preview them, then hit Publish. (For richer, "
        reply += "free-form edits, add an OpenAI key.)"
    else:
        reply = ("I can change the site's colors, font, announcement bar, and landing copy. "
                 "Try “make the whole site midnight black with ember-gold accents” or "
                 "“announce our Friday drop”. (Add an OpenAI key for fully free-form edits.)")
    return {
        "reply": reply,
        "updates": updates,
        "ideas": ["Make it feel more premium", "Write a bold new headline", "Announce a live drop"],
        "source": "rules",
    }


def site_studio(message: str, current: dict, fields: list[dict]) -> dict:
    """Turn a plain-English request into whole-site updates (content + theme).

    Returns {reply, updates, ideas, source}. Only whitelisted keys are returned;
    colour keys are validated as #RRGGBB. Never persists — the caller previews
    then publishes.
    """
    keys = {f["key"] for f in fields}
    color_keys = {f["key"] for f in fields if f.get("type") == "color"}
    keydoc = "; ".join(f"{f['key']} = {f['label']}" for f in fields)
    cur = {k: current.get(k) for k in keys}

    content = _chat([
        {"role": "system", "content":
            "You are RAGNAR Studio, the in-house design + copy assistant for RAGNAR, a bold "
            "Norse-themed trading-card marketplace ('a better eBay + Whatnot'). Staff talk to "
            "you to sculpt the ENTIRE website — its look and its words. Be imaginative and "
            "decisive: it's good to change several keys at once for one cohesive vibe. "
            f"Editable keys: {keydoc}. "
            "Color keys MUST be #RRGGBB hex that looks great on the UI. theme_font is a real "
            "Google Font family name. Keep copy punchy and on-brand; no emojis in copy fields. "
            "Return ONLY JSON: {\"reply\": one friendly sentence on what you changed, "
            "\"updates\": {key: value} for ONLY the keys you change, "
            "\"ideas\": [2-3 short next-move suggestions]}. "
            f"Current values: {json.dumps(cur)}."},
        {"role": "user", "content": message},
    ], max_tokens=600, temperature=0.85)

    if content:
        try:
            m = re.search(r"\{.*\}", content, re.DOTALL)
            d = json.loads(m.group(0) if m else content)
            updates = {}
            for k, v in (d.get("updates") or {}).items():
                if k not in keys or v is None:
                    continue
                v = str(v)
                if k in color_keys and not _HEX_RE.match(v):
                    continue
                updates[k] = v[:4000]
            ideas = [str(i)[:80] for i in (d.get("ideas") or [])][:3]
            return {
                "reply": (d.get("reply") or "Here are some changes — preview and publish.")[:400],
                "updates": updates,
                "ideas": ideas,
                "source": "openai",
            }
        except Exception:  # noqa: BLE001
            pass
    return _rules_studio(message, current, fields)


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

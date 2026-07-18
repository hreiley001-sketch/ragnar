"""Card recognition for scan-to-post.

Turns an uploaded photo into best-effort structured listing fields. Two paths:

  * OpenAI vision (if configured) — high accuracy, returns structured JSON.
  * Heuristic fallback — parses the filename + obvious tokens so the flow works
    with zero external dependencies. Clearly low-confidence; the UI asks the
    seller to confirm.

Both return the SAME shape, so callers don't care which ran. This is the seam
to drop in a dedicated card-recognition API (e.g. Ximilar) later.
"""
from __future__ import annotations

import base64
import json
import logging
import re
from pathlib import Path

import httpx

from .config import settings
from .models import Category, Condition, GradingCompany

logger = logging.getLogger("ragnar.scan")

_CATEGORY_HINTS = {
    "pokemon": Category.pokemon.value,
    "pokémon": Category.pokemon.value,
    "pkmn": Category.pokemon.value,
    "mtg": Category.magic.value,
    "magic": Category.magic.value,
    "yugioh": Category.yugioh.value,
    "yu-gi-oh": Category.yugioh.value,
    "ygo": Category.yugioh.value,
    "onepiece": Category.one_piece.value,
    "lorcana": Category.lorcana.value,
    "nba": Category.basketball.value,
    "basketball": Category.basketball.value,
    "mlb": Category.baseball.value,
    "baseball": Category.baseball.value,
    "nfl": Category.football.value,
    "football": Category.football.value,
    "soccer": Category.soccer.value,
    "fifa": Category.soccer.value,
}

_VALID_CATEGORIES = {c.value for c in Category}
_VALID_CONDITIONS = {c.value for c in Condition}
_VALID_GRADERS = {g.value for g in GradingCompany}


def _empty_fields() -> dict:
    return {
        "title": None,
        "category": None,
        "set_name": None,
        "card_number": None,
        "player_or_character": None,
        "year": None,
        "is_graded": False,
        "condition": None,
        "grading_company": None,
        "grade": None,
    }


def _coerce_fields(raw: dict) -> dict:
    """Snap free-form recognizer output onto our taxonomy where possible."""
    fields = _empty_fields()
    fields.update({k: raw.get(k) for k in fields if k in raw})

    if fields["category"] and fields["category"] not in _VALID_CATEGORIES:
        low = str(fields["category"]).lower()
        fields["category"] = next(
            (v for k, v in _CATEGORY_HINTS.items() if k in low), None
        )
    if fields["condition"] and fields["condition"] not in _VALID_CONDITIONS:
        fields["condition"] = None
    if fields["grading_company"]:
        gc = str(fields["grading_company"]).upper()
        fields["grading_company"] = gc if gc in _VALID_GRADERS else None
    if fields["grading_company"] or fields["grade"] is not None:
        fields["is_graded"] = True
    try:
        if fields["grade"] is not None:
            fields["grade"] = float(fields["grade"])
    except (TypeError, ValueError):
        fields["grade"] = None
    try:
        if fields["year"] is not None:
            fields["year"] = int(fields["year"])
    except (TypeError, ValueError):
        fields["year"] = None
    return fields


# --------------------------------------------------------------------------- #
# Heuristic (no external dependency)
# --------------------------------------------------------------------------- #


def _heuristic(filename: str) -> dict:
    stem = Path(filename or "").stem
    tokens = [t for t in re.split(r"[-_.\s]+", stem) if t]
    low = stem.lower()
    fields = _empty_fields()
    used = set()

    # Category
    for k, v in _CATEGORY_HINTS.items():
        if k in low:
            fields["category"] = v
            break

    # Grading company + grade (e.g. "psa10", "bgs-9.5")
    m = re.search(r"\b(psa|bgs|sgc|cgc|tag)[\s_-]*([0-9]{1,2}(?:\.5)?)?\b", low)
    if m:
        fields["grading_company"] = m.group(1).upper()
        fields["is_graded"] = True
        if m.group(2):
            fields["grade"] = float(m.group(2))
        used.update({m.group(1)})

    # Year
    y = re.search(r"\b(19[5-9]\d|20[0-4]\d)\b", low)
    if y:
        fields["year"] = int(y.group(1))
        used.add(y.group(1))

    # Card number like 4/102 or 215/203
    n = re.search(r"\b(\d{1,3}/\d{1,3})\b", low)
    if n:
        fields["card_number"] = n.group(1)
        used.add(n.group(1))

    # Remaining alphabetic tokens -> name/title guess
    name_tokens = [
        t for t in tokens
        if t.lower() not in used
        and not re.fullmatch(r"[0-9./]+", t)
        and not re.fullmatch(r"(psa|bgs|sgc|cgc|tag)\d{1,2}(?:\.5)?", t.lower())
        and t.lower() not in _CATEGORY_HINTS
        and t.lower() not in {"psa", "bgs", "sgc", "cgc", "tag", "img", "photo", "scan", "front", "back"}
    ]
    if name_tokens:
        guess = " ".join(name_tokens).title()
        fields["player_or_character"] = guess
        fields["title"] = guess

    has_signal = any(
        fields[k] for k in ("category", "grading_company", "year", "card_number", "player_or_character")
    )
    return {
        "fields": _coerce_fields(fields),
        "confidence": 0.35 if has_signal else 0.1,
        "provider": "heuristic",
        "notes": "Best-effort auto-fill from the file name (no vision provider "
        "configured). Please confirm the details before publishing.",
    }


# --------------------------------------------------------------------------- #
# OpenAI vision
# --------------------------------------------------------------------------- #

_VISION_PROMPT = (
    "You are a trading-card cataloguer. Identify the card in this image and "
    "return ONLY compact JSON with these keys: title, category, set_name, "
    "card_number, player_or_character, year, is_graded, condition, "
    "grading_company, grade. "
    f"category must be one of {sorted(_VALID_CATEGORIES)}. "
    f"If graded, grading_company must be one of {sorted(_VALID_GRADERS)} and grade a number. "
    f"If ungraded, condition should be one of {sorted(_VALID_CONDITIONS)}. "
    "Use null for anything you cannot read. Do not invent a grade."
)


def _openai_vision(image_bytes: bytes, content_type: str) -> dict | None:
    if not settings.openai_api_key:
        return None
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{content_type or 'image/jpeg'};base64,{b64}"
    payload = {
        "model": settings.openai_vision_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _VISION_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "max_tokens": 400,
        "temperature": 0,
    }
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    try:
        with httpx.Client(timeout=45.0) as client:
            resp = client.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers=headers,
            )
        if resp.status_code >= 400:
            logger.warning("OpenAI vision failed %s: %s", resp.status_code, resp.text[:200])
            return None
        content = resp.json()["choices"][0]["message"]["content"]
        match = re.search(r"\{.*\}", content, re.DOTALL)
        raw = json.loads(match.group(0) if match else content)
        return {
            "fields": _coerce_fields(raw),
            "confidence": 0.82,
            "provider": f"openai:{settings.openai_vision_model}",
            "notes": "Auto-identified by vision model. Please confirm before publishing.",
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("OpenAI vision error: %s", exc)
        return None


# --------------------------------------------------------------------------- #
# Ximilar collectibles recognition
# --------------------------------------------------------------------------- #

# Map likely provider keys -> our field names (checked case-insensitively).
_XIMILAR_KEY_MAP = {
    "title": ("full_name", "name", "title", "card"),
    "set_name": ("set_name", "set", "series", "set name"),
    "card_number": ("card_number", "number", "card number", "card_id"),
    "player_or_character": ("subcategory", "player", "name", "character"),
    "year": ("year",),
    "grading_company": ("company", "grading_company", "grader", "grading company"),
    "grade": ("grade",),
    "category": ("category", "top category", "subcategory"),
}


def _deep_find(node, keys: tuple[str, ...]):
    """First value in a nested dict/list whose (lowercased) key matches `keys`."""
    lowered = {k.lower() for k in keys}
    stack = [node]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                if isinstance(k, str) and k.lower() in lowered and v not in (None, "", []):
                    if not isinstance(v, (dict, list)):
                        return v
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return None


def _ximilar(image_bytes: bytes, content_type: str) -> dict | None:
    if not settings.ximilar_token:
        return None
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    url = f"{settings.ximilar_base}/{settings.ximilar_endpoint.strip('/')}"
    headers = {"Authorization": f"Token {settings.ximilar_token}"}
    body = {"records": [{"_base64": b64}]}
    try:
        with httpx.Client(timeout=45.0) as client:
            resp = client.post(url, json=body, headers=headers)
        if resp.status_code >= 400:
            logger.warning("Ximilar failed %s: %s", resp.status_code, resp.text[:200])
            return None
        payload = resp.json()
        if settings.debug:
            logger.info("Ximilar raw response: %s", json.dumps(payload)[:1500])

        raw = {
            target: _deep_find(payload, keys)
            for target, keys in _XIMILAR_KEY_MAP.items()
        }
        prob = _deep_find(payload, ("prob", "_probability", "score", "distance"))
        confidence = 0.85
        try:
            if prob is not None and 0 <= float(prob) <= 1:
                confidence = round(0.5 + 0.5 * float(prob), 2)
        except (TypeError, ValueError):
            pass
        fields = _coerce_fields({k: v for k, v in raw.items() if v is not None})
        if not any(fields.get(k) for k in ("title", "player_or_character", "set_name")):
            # Nothing usable came back — let a fallback try.
            return None
        return {
            "fields": fields,
            "confidence": confidence,
            "provider": f"ximilar:{settings.ximilar_endpoint}",
            "notes": "Auto-identified by Ximilar collectibles recognition. "
            "Confirm details before publishing.",
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("Ximilar error: %s", exc)
        return None


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def active_provider() -> str:
    """Which recognizer will run given current config (for status/UI)."""
    p = settings.scan_provider
    if p in {"auto", "ximilar"} and settings.ximilar_token:
        return "ximilar"
    if p in {"auto", "openai"} and settings.openai_api_key:
        return "openai"
    return "heuristic"


def recognize(image_bytes: bytes, filename: str, content_type: str) -> dict:
    provider = settings.scan_provider

    # 1) Ximilar (specialized) — preferred in auto mode when configured.
    if provider in {"auto", "ximilar"} and settings.ximilar_token:
        result = _ximilar(image_bytes, content_type)
        if result:
            return result
        if provider == "ximilar":
            fb = _heuristic(filename)
            fb["notes"] = "Ximilar unavailable; " + fb["notes"]
            return fb

    # 2) OpenAI vision.
    if provider in {"auto", "openai"} and settings.openai_api_key:
        result = _openai_vision(image_bytes, content_type)
        if result:
            return result
        if provider == "openai":
            fb = _heuristic(filename)
            fb["notes"] = "Vision provider unavailable; " + fb["notes"]
            return fb

    # 3) Heuristic fallback (always available).
    return _heuristic(filename)

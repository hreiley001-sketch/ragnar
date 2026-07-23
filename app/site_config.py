"""Staff-editable site content — a whitelisted registry.

Staff edit *content* (announcement, landing copy, community links), never code.
Only keys defined in ``SITE_FIELDS`` can be read or written; anything else is
ignored. Public pages hydrate from ``get_all()``; the Command Hub renders its
editor from ``field_specs()``.
"""
from __future__ import annotations

import re

from sqlmodel import Session, select

from . import cache as app_cache
from .models import SiteSetting, utcnow

_SITE_CONFIG_CACHE_KEY = "site_config:public"
_SITE_CONFIG_TTL = 45.0

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

# key, label, input type, group, default, help. `type` drives the hub UI widget.
SITE_FIELDS: list[dict] = [
    {
        "key": "announcement",
        "label": "Announcement bar",
        "type": "text",
        "group": "Global",
        "default": "",
        "help": "Shown as a gold banner on every page. Leave blank to hide it.",
    },
    {
        "key": "announcement_link",
        "label": "Announcement link (optional)",
        "type": "url",
        "group": "Global",
        "default": "",
        "help": "If set, the announcement bar becomes clickable.",
    },
    {
        "key": "hero_headline",
        "label": "Landing headline",
        "type": "text",
        "group": "Landing page",
        "default": "Be one of the 250 Founding Sellers.",
        "help": "Big headline on the front door.",
    },
    {
        "key": "hero_subtitle",
        "label": "Landing subtitle",
        "type": "textarea",
        "group": "Landing page",
        "default": "RAGNAR is a trust-first marketplace for trading cards — built so "
                   "sellers keep more and buyers stop getting burned. The first 250 "
                   "sellers lock in founding status forever.",
        "help": "Supporting sentence under the headline.",
    },
    {
        "key": "discord_url",
        "label": "Discord invite URL",
        "type": "url",
        "group": "Community",
        "default": "",
    },
    {
        "key": "instagram_url",
        "label": "Instagram URL",
        "type": "url",
        "group": "Community",
        "default": "",
    },
    {
        "key": "support_email",
        "label": "Support email",
        "type": "text",
        "group": "Community",
        "default": "henry@ragnarips.com",
    },
    # --- Homepage perk cards (the four boxes under the hero) ---
    {"key": "perk1_title", "label": "Perk 1 title", "type": "text", "group": "Homepage perks", "default": "Fees for 90 days"},
    {"key": "perk1_desc", "label": "Perk 1 detail", "type": "text", "group": "Homepage perks", "default": "Pay only payment processing during your intro window — keep the rest."},
    {"key": "perk2_title", "label": "Perk 2 title", "type": "text", "group": "Homepage perks", "default": "Permanent founding rate"},
    {"key": "perk2_desc", "label": "Perk 2 detail", "type": "text", "group": "Homepage perks", "default": "A lower rate than everyone else, locked in for good — our thank-you for being early."},
    {"key": "perk3_title", "label": "Perk 3 title", "type": "text", "group": "Homepage perks", "default": "Founding badge"},
    {"key": "perk3_desc", "label": "Perk 3 detail", "type": "text", "group": "Homepage perks", "default": "A permanent Founding Seller badge on your storefront. Status that never expires."},
    {"key": "perk4_title", "label": "Perk 4 title", "type": "text", "group": "Homepage perks", "default": "Your own store"},
    {"key": "perk4_desc", "label": "Perk 4 detail", "type": "text", "group": "Homepage perks", "default": "A customizable storefront, scan-to-list, real sold-price history, and live selling."},
    # --- Look & feel: applied site-wide as CSS variables by nav.js ---
    {
        "key": "theme_accent",
        "label": "Accent color",
        "type": "color",
        "group": "Look & feel",
        "default": "#8a6510",
        "help": "Primary highlight — buttons, links, prices.",
    },
    {
        "key": "theme_gold",
        "label": "Gold / badge color",
        "type": "color",
        "group": "Look & feel",
        "default": "#b8791a",
    },
    {
        "key": "theme_bg",
        "label": "Background",
        "type": "color",
        "group": "Look & feel",
        "default": "#f5f1e8",
    },
    {
        "key": "theme_text",
        "label": "Text color",
        "type": "color",
        "group": "Look & feel",
        "default": "#221a10",
    },
    {
        "key": "theme_font",
        "label": "Site font",
        "type": "text",
        "group": "Look & feel",
        "default": "",
        "help": "A Google Font family, e.g. 'Space Grotesk'. Blank = default.",
    },
]

# Keys whose values must be a #RRGGBB color (validated on save + by the studio).
COLOR_KEYS: set[str] = {f["key"] for f in SITE_FIELDS if f["type"] == "color"}

DEFAULTS: dict[str, str] = {f["key"]: f["default"] for f in SITE_FIELDS}
ALLOWED: set[str] = set(DEFAULTS)
_MAX_LEN = 4000


# Theme values shipped as defaults in earlier brand eras (blue → glacial dark →
# interim gold). Stored rows matching these were written by a past deploy, not
# hand-picked by staff, so we retire them on startup and let the current DEFAULTS
# apply. Deliberately custom colors (anything not in this set) are preserved.
_LEGACY_THEME_VALUES: dict[str, set[str]] = {
    "theme_accent": {"#2563eb", "#8ecae6", "#9a6b12", "#6fd6ff"},
    "theme_gold": {"#b8791a", "#d4a574", "#f0c674"},
    "theme_bg": {"#f5f7fa", "#2f4d68", "#1a2d42", "#0a0f16", "#05070b", "#12161d"},
    "theme_text": {"#131a24", "#f4f8fb", "#dfe8f2"},
}


def retire_legacy_theme_values(session: Session) -> int:
    """Delete stored ``theme_*`` rows whose value matches a known prior-era
    default, so the current DEFAULTS take effect after a rebrand deploy. Rows a
    staff member deliberately customized (values not in the legacy set) survive.
    Returns the number of rows removed."""
    removed = 0
    for row in session.exec(select(SiteSetting)).all():
        legacy = _LEGACY_THEME_VALUES.get(row.key)
        if legacy is not None and row.value in legacy:
            session.delete(row)
            removed += 1
    if removed:
        session.commit()
    return removed


def get_all(session: Session, *, use_cache: bool = True) -> dict[str, str]:
    """Every whitelisted key merged over its default (public-safe)."""
    if use_cache:
        hit = app_cache.get(_SITE_CONFIG_CACHE_KEY)
        if isinstance(hit, dict):
            return hit

    out = dict(DEFAULTS)
    for row in session.exec(select(SiteSetting)).all():
        if row.key in ALLOWED:
            out[row.key] = row.value
    if use_cache:
        app_cache.set(_SITE_CONFIG_CACHE_KEY, out, ttl_seconds=_SITE_CONFIG_TTL)
    return out


def field_specs(session: Session) -> list[dict]:
    """Registry + current values, for rendering the Command Hub editor."""
    values = get_all(session)
    meta = {r.key: r for r in session.exec(select(SiteSetting)).all()}
    specs = []
    for f in SITE_FIELDS:
        row = meta.get(f["key"])
        specs.append({
            **f,
            "value": values[f["key"]],
            "updated_by": row.updated_by if row else None,
            "updated_at": row.updated_at.isoformat() if row else None,
        })
    return specs


def set_many(session: Session, updates: dict, by: str | None) -> dict[str, str]:
    """Persist whitelisted key/values. Unknown keys are ignored. Returns the
    full merged config."""
    now = utcnow()
    for key, value in (updates or {}).items():
        if key not in ALLOWED:
            continue
        value = ("" if value is None else str(value))[:_MAX_LEN]
        # Color fields must be valid hex, or we skip them (never store junk that
        # would break the site theme).
        if key in COLOR_KEYS and value and not _HEX_RE.match(value):
            continue
        row = session.get(SiteSetting, key)
        if row:
            row.value = value
            row.updated_by = by
            row.updated_at = now
        else:
            row = SiteSetting(key=key, value=value, updated_by=by, updated_at=now)
        session.add(row)
    session.commit()
    app_cache.invalidate(_SITE_CONFIG_CACHE_KEY)
    try:
        from .platform.cache import invalidate

        invalidate("site-config:public")
    except Exception:  # noqa: BLE001
        pass
    return get_all(session, use_cache=False)
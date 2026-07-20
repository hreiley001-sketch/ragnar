"""Staff-editable site content — a whitelisted registry.

Staff edit *content* (announcement, landing copy, community links), never code.
Only keys defined in ``SITE_FIELDS`` can be read or written; anything else is
ignored. Public pages hydrate from ``get_all()``; the Command Hub renders its
editor from ``field_specs()``.
"""
from __future__ import annotations

import re

from sqlmodel import Session, select

from .models import SiteSetting, utcnow

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

# key, label, input type, group, default, help. `type` drives the hub UI widget.
SITE_FIELDS: list[dict] = [
    {
        "key": "announcement",
        "label": "Announcement bar",
        "type": "text",
        "group": "Global",
        "default": "",
        "help": "Shown as a frost banner on every page. Leave blank to hide it.",
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
        "default": "The future of sports card breaking.",
        "help": "Big headline on the front door.",
    },
    {
        "key": "hero_subtitle",
        "label": "Landing subtitle",
        "type": "textarea",
        "group": "Landing page",
        "default": "Enter the most exclusive trading-card marketplace in the world. "
                   "Sellers keep 95%. One flat 5% fee. Precision commerce, carved from ice.",
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
    {"key": "perk1_title", "label": "Perk 1 title", "type": "text", "group": "Homepage perks", "default": "Sellers keep 95%"},
    {"key": "perk1_desc", "label": "Perk 1 detail", "type": "text", "group": "Homepage perks", "default": "A simple flat 5% seller fee. Premium. Easy to understand."},
    {"key": "perk2_title", "label": "Perk 2 title", "type": "text", "group": "Homepage perks", "default": "5% flat seller fee"},
    {"key": "perk2_desc", "label": "Perk 2 detail", "type": "text", "group": "Homepage perks", "default": "One transparent rate. No category maze. No surprise tiers."},
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
        "default": "#4eb6e8",
        "help": "Primary highlight — buttons, links, prices. Default icy blue from the RAGNAR logo: #4eb6e8.",
    },
    {
        "key": "theme_gold",
        "label": "Titanium / badge color",
        "type": "color",
        "group": "Look & feel",
        "default": "#a8bccb",
    },
    {
        "key": "theme_bg",
        "label": "Background",
        "type": "color",
        "group": "Look & feel",
        "default": "#151c26",
    },
    {
        "key": "theme_text",
        "label": "Text color",
        "type": "color",
        "group": "Look & feel",
        "default": "#f2f7fc",
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


def get_all(session: Session) -> dict[str, str]:
    """Every whitelisted key merged over its default (public-safe)."""
    out = dict(DEFAULTS)
    for row in session.exec(select(SiteSetting)).all():
        if row.key in ALLOWED:
            out[row.key] = row.value
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
    return get_all(session)

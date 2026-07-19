"""Staff-editable site content — a whitelisted registry.

Staff edit *content* (announcement, landing copy, community links), never code.
Only keys defined in ``SITE_FIELDS`` can be read or written; anything else is
ignored. Public pages hydrate from ``get_all()``; the Command Hub renders its
editor from ``field_specs()``.
"""
from __future__ import annotations

from sqlmodel import Session, select

from .models import SiteSetting, utcnow

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
]

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

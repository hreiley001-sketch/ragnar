"""Supabase client + pooled connection hints (Birdman data spine)."""
from __future__ import annotations

import logging
from typing import Any

from .config import settings
from .security import service_headers, verify_bearer_jwt

logger = logging.getLogger("ragnar.core.database")


def supabase_status() -> dict[str, Any]:
    url = settings.supabase_url
    return {
        "enabled": bool(url),
        "url": url or None,
        "jwt_configured": bool(settings.supabase_jwt_secret),
        "anon_key_configured": bool(settings.supabase_anon_key),
        "secret_key_configured": bool(settings.supabase_secret_key),
        "db_url_configured": bool(settings.supabase_db_url),
        "db_active": bool(settings.use_supabase_db and settings.supabase_db_url),
        "pooling": "transaction" if settings.supabase_db_url else None,
    }


def database_url_for_sqlalchemy() -> str | None:
    """Pooled Supabase Postgres URL when configured (port 6543 preferred)."""
    raw = settings.supabase_db_url
    if not raw:
        return None
    from urllib.parse import quote, urlparse, urlunparse

    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://") :]
    u = urlparse(raw)
    if u.password:
        user = quote(u.username or "", safe="")
        password = quote(u.password, safe="")
        host = u.hostname or ""
        port = f":{u.port}" if u.port else ""
        netloc = f"{user}:{password}@{host}{port}"
        raw = urlunparse((u.scheme, netloc, u.path, u.params, u.query, u.fragment))
    if raw.startswith("postgresql://") and "+psycopg" not in raw.split("://", 1)[0]:
        raw = "postgresql+psycopg://" + raw[len("postgresql://") :]
    return raw


# Back-compat aliases used by platform shims
verify_jwt = verify_bearer_jwt
status = supabase_status

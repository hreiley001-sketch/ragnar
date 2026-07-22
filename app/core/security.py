"""JWT verification + auth utilities (Birdman security spine)."""
from __future__ import annotations

import logging
from typing import Any

from .config import settings

logger = logging.getLogger("ragnar.core.security")


def verify_bearer_jwt(token: str) -> dict[str, Any] | None:
    """Verify a Supabase-issued access token. Returns claims or None."""
    secret = settings.supabase_jwt_secret
    if not secret or not token:
        return None
    try:
        import jwt  # PyJWT
    except ImportError:
        logger.warning("PyJWT not installed — cannot verify Supabase tokens")
        return None

    try:
        return jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"require": ["exp", "sub"]},
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("jwt reject: %s", exc)
        return None


def extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.strip().split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def service_headers() -> dict[str, str] | None:
    """Headers for server-side Supabase REST/Auth (secret preferred)."""
    key = settings.supabase_secret_key or settings.supabase_anon_key
    if not settings.supabase_url or not key:
        return None
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

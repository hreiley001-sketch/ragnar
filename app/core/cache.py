"""Redis client + JSON cache — short memory for the organism."""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from .config import settings

logger = logging.getLogger("ragnar.core.cache")

T = TypeVar("T")
PREFIX = "birdman:cache:"

_client: Any | None = None
_failed = False


def get_redis():
    """Return a shared Redis client, or None if unavailable."""
    global _client, _failed
    if _failed:
        return None
    if _client is not None:
        return _client
    url = settings.redis_url
    if not url:
        return None
    try:
        import redis  # type: ignore

        _client = redis.Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=1.5,
            socket_timeout=1.5,
        )
        _client.ping()
        logger.info("Redis connected")
        return _client
    except Exception as exc:  # noqa: BLE001
        _failed = True
        logger.warning("Redis unavailable: %s", exc)
        return None


def redis_ping() -> dict:
    r = get_redis()
    if r is None:
        return {"enabled": bool(settings.redis_url), "ok": False, "mode": "off"}
    try:
        r.ping()
        return {"enabled": True, "ok": True, "mode": "redis"}
    except Exception as exc:  # noqa: BLE001
        return {"enabled": True, "ok": False, "mode": "redis", "error": str(exc)}


def reset_redis() -> None:
    global _client, _failed
    _client = None
    _failed = False


def cached_json(
    key: str,
    *,
    ttl_seconds: int,
    loader: Callable[[], T],
) -> T:
    """Return cached JSON for ``key``, else call ``loader`` and store.

    TTL is always explicit. On Redis miss/failure, loader runs (truth path).
    """
    if ttl_seconds <= 0:
        return loader()
    full = PREFIX + key
    r = get_redis()
    if r is not None:
        try:
            raw = r.get(full)
            if raw is not None:
                return json.loads(raw)  # type: ignore[return-value]
        except Exception as exc:  # noqa: BLE001
            logger.warning("cache get failed %s: %s", key, exc)

    value = loader()
    if r is not None:
        try:
            r.setex(full, ttl_seconds, json.dumps(value, default=str))
        except Exception as exc:  # noqa: BLE001
            logger.warning("cache set failed %s: %s", key, exc)
    return value


def invalidate(*keys: str) -> int:
    r = get_redis()
    if r is None or not keys:
        return 0
    full = [PREFIX + k for k in keys]
    try:
        return int(r.delete(*full))
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache invalidate failed: %s", exc)
        return 0

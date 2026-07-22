"""Shim → ``app.core.cache`` (Birdman spine)."""
from __future__ import annotations

from app.core.cache import PREFIX, cached_json, get_redis, invalidate, redis_ping, reset_redis

reset = reset_redis

__all__ = [
    "PREFIX",
    "cached_json",
    "get_redis",
    "invalidate",
    "redis_ping",
    "reset",
    "reset_redis",
]

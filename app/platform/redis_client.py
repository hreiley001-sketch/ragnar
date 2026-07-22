"""Shim → ``app.core.cache`` Redis helpers."""
from __future__ import annotations

from app.core.cache import get_redis, redis_ping, reset_redis

ping = redis_ping
reset = reset_redis

__all__ = ["get_redis", "ping", "reset", "redis_ping", "reset_redis"]

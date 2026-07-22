"""Shared response / object cache for high-traffic reads.

Prefer Redis when ``REDIS_URL`` is set (required for multi-node). Falls back to
a process-local TTL dict for single-node development only — that fallback is
**not** shared across replicas and must not be relied on in production.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Callable, Optional, TypeVar

from .config import settings

logger = logging.getLogger("ragnar.cache")

T = TypeVar("T")

# Explicit invalidation namespaces used across routers.
NS_META = "meta"
NS_FOUNDING = "founding:status"
NS_LISTINGS = "listings"
NS_SITE_CONFIG = "site-config"


class _MemoryStore:
    """Dev-only TTL map. Not shared across workers."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, tuple[float, str]] = {}

    def get(self, key: str) -> Optional[str]:
        now = time.monotonic()
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            expires, value = item
            if expires < now:
                self._data.pop(key, None)
                return None
            return value

    def set(self, key: str, value: str, ttl: int) -> None:
        with self._lock:
            self._data[key] = (time.monotonic() + max(1, ttl), value)

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def delete_prefix(self, prefix: str) -> int:
        with self._lock:
            keys = [k for k in self._data if k.startswith(prefix)]
            for k in keys:
                del self._data[k]
            return len(keys)

    def ping(self) -> bool:
        return True


class _RedisStore:
    def __init__(self, url: str) -> None:
        import redis  # lazy — optional dependency at import time of app

        self._client = redis.Redis.from_url(url, decode_responses=True)

    def get(self, key: str) -> Optional[str]:
        return self._client.get(key)

    def set(self, key: str, value: str, ttl: int) -> None:
        self._client.setex(key, max(1, ttl), value)

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def delete_prefix(self, prefix: str) -> int:
        # SCAN avoids KEYS blocking Redis under load.
        deleted = 0
        cursor = 0
        pattern = f"{prefix}*"
        while True:
            cursor, keys = self._client.scan(cursor=cursor, match=pattern, count=200)
            if keys:
                deleted += int(self._client.delete(*keys))
            if cursor == 0:
                break
        return deleted

    def ping(self) -> bool:
        return bool(self._client.ping())


_store: _MemoryStore | _RedisStore | None = None
_store_kind = "none"


def _ensure_store() -> _MemoryStore | _RedisStore:
    global _store, _store_kind
    if _store is not None:
        return _store
    url = (settings.redis_url or "").strip()
    if url:
        try:
            _store = _RedisStore(url)
            _store.ping()
            _store_kind = "redis"
            logger.info("Cache backend: redis")
            return _store
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis unavailable (%s); falling back to memory cache", exc)
    _store = _MemoryStore()
    _store_kind = "memory"
    if settings.is_production:
        logger.warning(
            "Cache backend: memory (not shared across FastAPI nodes — set REDIS_URL)"
        )
    return _store


def backend() -> str:
    _ensure_store()
    return _store_kind


def cache_key(*parts: Any) -> str:
    return ":".join(str(p) for p in parts if p is not None and p != "")


def get_json(key: str) -> Any | None:
    raw = _ensure_store().get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def set_json(key: str, value: Any, ttl: int | None = None) -> None:
    ttl_s = int(ttl if ttl is not None else settings.cache_default_ttl_seconds)
    _ensure_store().set(key, json.dumps(value, default=str), ttl_s)


def delete(key: str) -> None:
    _ensure_store().delete(key)


def invalidate_prefix(prefix: str) -> int:
    """Drop all keys under ``prefix`` (explicit invalidation rule)."""
    return _ensure_store().delete_prefix(prefix)


def invalidate_listings() -> int:
    return invalidate_prefix(f"{NS_LISTINGS}:")


def invalidate_meta() -> int:
    delete(NS_META)
    return 1


def invalidate_founding() -> int:
    delete(NS_FOUNDING)
    return 1


def cached_json(key: str, producer: Callable[[], T], *, ttl: int | None = None) -> T:
    hit = get_json(key)
    if hit is not None:
        return hit  # type: ignore[return-value]
    value = producer()
    # Pydantic / SQLModel objects → dict via model_dump when present.
    if hasattr(value, "model_dump"):
        payload: Any = value.model_dump()
    else:
        payload = value
    set_json(key, payload, ttl=ttl)
    return value

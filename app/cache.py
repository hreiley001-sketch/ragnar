"""Tiny in-process TTL cache for hot, mostly-static API payloads.

No Redis required. Fine for a single worker; multi-worker deploys each keep
their own short-lived copy (admin writes invalidate locally; TTL bounds drift).
"""
from __future__ import annotations

import threading
import time
from typing import Any

_lock = threading.Lock()
_store: dict[str, tuple[float, Any]] = {}


def get(key: str) -> Any | None:
    now = time.monotonic()
    with _lock:
        item = _store.get(key)
        if not item:
            return None
        expires, value = item
        if expires < now:
            _store.pop(key, None)
            return None
        return value


def set(key: str, value: Any, ttl_seconds: float = 45.0) -> None:
    with _lock:
        _store[key] = (time.monotonic() + max(0.1, ttl_seconds), value)


def invalidate(*keys: str) -> None:
    with _lock:
        if not keys:
            _store.clear()
            return
        for key in keys:
            _store.pop(key, None)


def get_or_set(key: str, factory, ttl_seconds: float = 45.0) -> Any:
    hit = get(key)
    if hit is not None:
        return hit
    value = factory()
    set(key, value, ttl_seconds=ttl_seconds)
    return value

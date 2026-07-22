"""Rate limiter — Redis when available (shared across FastAPI nodes), else
process-local sliding window (dev / single-node only).

At 100k concurrent viewers the in-process limiter is insufficient; set REDIS_URL
and terminate TLS / DDoS at Cloudflare in front of the load balancer.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import HTTPException, Request, status

from .config import settings

logger = logging.getLogger("ragnar.ratelimit")


class _MemoryLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    def hit(self, key: str, *, limit: int, window_seconds: int) -> None:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            q = self._hits[key]
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many requests. Try again in {window_seconds // 60 or 1} minute(s).",
                )
            q.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


class _RedisLimiter:
    """Fixed-window counter via INCR + EXPIRE (good enough for auth/checkout)."""

    def __init__(self, url: str) -> None:
        import redis

        self._client = redis.Redis.from_url(url, decode_responses=True)

    def hit(self, key: str, *, limit: int, window_seconds: int) -> None:
        rk = f"rl:{key}:{window_seconds}"
        pipe = self._client.pipeline()
        pipe.incr(rk)
        pipe.expire(rk, window_seconds, nx=True)
        count, _ = pipe.execute()
        if int(count) > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many requests. Try again in {window_seconds // 60 or 1} minute(s).",
            )

    def reset(self) -> None:
        # Best-effort clear of rl:* keys (tests / admin).
        cursor = 0
        while True:
            cursor, keys = self._client.scan(cursor=cursor, match="rl:*", count=200)
            if keys:
                self._client.delete(*keys)
            if cursor == 0:
                break


class RateLimiter:
    def __init__(self) -> None:
        self._backend: _MemoryLimiter | _RedisLimiter | None = None

    def _ensure(self) -> _MemoryLimiter | _RedisLimiter:
        if self._backend is not None:
            return self._backend
        url = (settings.redis_url or "").strip()
        if url:
            try:
                self._backend = _RedisLimiter(url)
                logger.info("Rate limiter backend: redis")
                return self._backend
            except Exception as exc:  # noqa: BLE001
                logger.warning("Redis rate limiter unavailable (%s); using memory", exc)
        self._backend = _MemoryLimiter()
        return self._backend

    def hit(self, key: str, *, limit: int, window_seconds: int) -> None:
        self._ensure().hit(key, limit=limit, window_seconds=window_seconds)

    def reset(self) -> None:
        self._ensure().reset()


limiter = RateLimiter()

# Defaults — overridable in tests via settings later if needed.
LOGIN_IP_LIMIT = 10
LOGIN_IP_WINDOW = 15 * 60
LOGIN_EMAIL_LIMIT = 5
LOGIN_EMAIL_WINDOW = 15 * 60
SIGNUP_IP_LIMIT = 5
SIGNUP_IP_WINDOW = 60 * 60
CHECKOUT_LIMIT = 20
CHECKOUT_WINDOW = 60 * 60
FORGOT_IP_LIMIT = 10
FORGOT_IP_WINDOW = 60 * 60


def client_ip(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    if request.client and request.client.host:
        return request.client.host
    return "unknown"

"""Simple in-process sliding-window rate limiter for auth and checkout."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import HTTPException, Request, status


class RateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    def hit(self, key: str, *, limit: int, window_seconds: int) -> None:
        """Record a hit; raise 429 if more than ``limit`` in the window."""
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

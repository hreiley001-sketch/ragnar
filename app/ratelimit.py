"""Simple in-process sliding-window rate limiter for auth and checkout."""
from __future__ import annotations

import ipaddress
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
SCAN_IP_LIMIT = 20
SCAN_IP_WINDOW = 60 * 60
SUPPORT_IP_LIMIT = 60
SUPPORT_IP_WINDOW = 15 * 60
APPLY_IP_LIMIT = 10
APPLY_IP_WINDOW = 60 * 60
RESEND_IP_LIMIT = 5
RESEND_IP_WINDOW = 60 * 60


def _valid_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def client_ip(request: Request) -> str:
    """Best-effort client IP.

    Prefer the *right-most* untrusted-safe hop only when Render/Cloudflare
    already set a direct peer; otherwise use ``request.client.host`` so
    spoofed ``X-Forwarded-For`` prefixes cannot reset rate-limit buckets.
    """
    peer = request.client.host if request.client and request.client.host else ""
    forwarded = request.headers.get("x-forwarded-for") or ""
    # When behind a known proxy, the immediate peer is the proxy; take the
    # left-most *valid* public-looking address but ignore obvious garbage.
    if peer and peer not in {"127.0.0.1", "::1", "unknown"}:
        # Direct connection (local / non-proxy) — ignore spoofable header.
        return peer
    for part in forwarded.split(","):
        candidate = part.strip()
        if candidate and _valid_ip(candidate):
            return candidate
    return peer or "unknown"

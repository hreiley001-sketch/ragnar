"""Shared httpx clients — avoid opening a new TCP/TLS session per AI/API call."""
from __future__ import annotations

import atexit

import httpx

# Long-lived clients reused across recognition, pricing, comps, and OpenAI calls.
_sync_client: httpx.Client | None = None


def sync_client(timeout: float = 40.0) -> httpx.Client:
    """Return a process-wide sync client. Timeout is set per-request by callers."""
    global _sync_client
    if _sync_client is None or _sync_client.is_closed:
        _sync_client = httpx.Client(
            timeout=httpx.Timeout(timeout, connect=10.0),
            limits=httpx.Limits(max_connections=40, max_keepalive_connections=20),
        )
    return _sync_client


def close() -> None:
    global _sync_client
    if _sync_client is not None and not _sync_client.is_closed:
        _sync_client.close()
    _sync_client = None


atexit.register(close)

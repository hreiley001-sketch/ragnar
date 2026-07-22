"""Shim — platform package now points at ``app.core``."""
from __future__ import annotations

from app.core.cache import cached_json, invalidate, redis_ping
from app.core.database import supabase_status
from app.core.queue import enqueue, n8n_status, queue_depth
from app.core.queue import _trigger_n8n as trigger_workflow

__all__ = [
    "cached_json",
    "enqueue",
    "invalidate",
    "n8n_status",
    "queue_depth",
    "redis_ping",
    "supabase_status",
    "trigger_workflow",
]

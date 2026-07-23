"""Realtime logic — pulse / future SSE for rides + events."""
from __future__ import annotations

from typing import Any

from app.core.cache import redis_ping
from app.core.database import supabase_status
from app.core.queue import n8n_status, queue_depth


def organism_pulse() -> dict[str, Any]:
    """Lightweight organ health for SSE/clients — no secrets."""
    return {
        "product": "ragnar",
        "organism": "birdman",
        "hub": "Maps/RAGNAR",
        "redis": redis_ping(),
        "queue": queue_depth(),
        "n8n": n8n_status(),
        "supabase": supabase_status(),
    }

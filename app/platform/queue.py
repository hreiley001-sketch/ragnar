"""Shim → ``app.core.queue``."""
from __future__ import annotations

from app.core.queue import dequeue, enqueue, n8n_status, queue_depth

__all__ = ["dequeue", "enqueue", "n8n_status", "queue_depth"]

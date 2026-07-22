"""Shim → ``app.core.queue`` n8n fire helpers."""
from __future__ import annotations

from app.core.queue import _trigger_n8n, n8n_status

trigger_workflow = _trigger_n8n
status = n8n_status

__all__ = ["status", "trigger_workflow"]

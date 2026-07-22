"""Platform-wide event fan-out (marketplace ops → n8n).

Distinct from the ride-scoped ``event_bus`` (which persists ``RideEvent`` rows).
This helper is intentionally thin and **always asynchronous** — FastAPI never
waits for n8n. See ``docs/ARCHITECTURE.md``.
"""
from __future__ import annotations

import logging
from typing import Any

from . import webhooks_out

logger = logging.getLogger("ragnar.platform_events")


def emit(event: str, data: dict[str, Any] | None = None) -> None:
    """Enqueue an external automation event. Never raises. Never blocks on n8n."""
    try:
        webhooks_out.enqueue(event, data)
    except Exception as exc:  # noqa: BLE001
        logger.warning("platform emit failed (%s): %s", event, exc)

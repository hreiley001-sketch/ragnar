"""Platform-wide event fan-out (marketplace ops → n8n / Obsidian).

Distinct from the ride-scoped ``event_bus`` (which persists ``RideEvent`` rows).
This helper is intentionally thin and fail-soft.
"""
from __future__ import annotations

import logging
from typing import Any

from . import webhooks_out

logger = logging.getLogger("ragnar.platform_events")


def emit(event: str, data: dict[str, Any] | None = None) -> None:
    """Notify external automation (n8n). Never raises."""
    try:
        webhooks_out.dispatch(event, data)
    except Exception as exc:  # noqa: BLE001
        logger.warning("platform emit failed (%s): %s", event, exc)

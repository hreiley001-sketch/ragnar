"""Settings, env, secrets — re-exports the living Settings object.

Source of truth remains ``app.config`` so marketplace + platform share one spine.
Import from ``app.core.config`` in new Birdman modules.
"""
from __future__ import annotations

from app.config import Settings, settings, validate_launch_config

__all__ = ["Settings", "settings", "validate_launch_config"]

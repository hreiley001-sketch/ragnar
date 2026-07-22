"""Realtime event shapes — Supabase ``realtime_events`` + SSE pulse."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class BirdmanRealtimeEvent(BaseModel):
    """Supabase ``public.realtime_events``."""

    id: UUID
    channel: str
    event_type: str
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


class RealtimePulse(BaseModel):
    """Organ health snapshot (api/v1/realtime/pulse)."""

    organism: str = "birdman"
    redis: dict[str, Any] = Field(default_factory=dict)
    queue: dict[str, Any] = Field(default_factory=dict)
    n8n: dict[str, Any] = Field(default_factory=dict)
    supabase: dict[str, Any] = Field(default_factory=dict)

"""System log shapes — Supabase ``system_logs``."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class BirdmanSystemLog(BaseModel):
    """Supabase ``public.system_logs`` — organism memory."""

    id: UUID
    source: str
    level: Literal["info", "warn", "error", "debug"] = "info"
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None

"""Action-shaped models — queue trigger + Supabase ``actions`` row."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ActionRequest(BaseModel):
    """FastAPI → Redis → n8n trigger (api/v1/actions)."""

    topic: str = Field(min_length=1, max_length=120, description="e.g. ops.notify")
    payload: dict[str, Any] = Field(default_factory=dict)
    workflow: Optional[str] = Field(
        default=None,
        description="n8n webhook path segment; defaults from topic",
    )


class ActionResult(BaseModel):
    ok: bool = True
    job_id: str
    topic: str
    workflow: str
    queued: bool = True


class BirdmanAction(BaseModel):
    """Supabase ``public.actions`` — atomic interaction / trigger."""

    id: UUID
    user_id: UUID
    content_id: Optional[UUID] = None
    action_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None

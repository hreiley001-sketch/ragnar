"""Action-shaped API models — writes that cross the async boundary."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ActionRequest(BaseModel):
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

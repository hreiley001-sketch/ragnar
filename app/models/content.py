"""Content-shaped models — API cache surface + Supabase ``content`` row."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ContentItem(BaseModel):
    """Cached content unit for api/v1/content (listings, site config, …)."""

    id: str
    kind: str = Field(description="listing | site_config | meta | content")
    title: Optional[str] = None
    data: dict[str, Any] = Field(default_factory=dict)


class ContentPage(BaseModel):
    items: list[ContentItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 24
    cached: bool = False


class BirdmanContent(BaseModel):
    """Supabase ``public.content`` — atomic content unit."""

    id: UUID
    author_id: UUID
    title: str
    body: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

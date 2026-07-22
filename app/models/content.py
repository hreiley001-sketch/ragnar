"""Content-shaped API models — cached reads surface."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ContentItem(BaseModel):
    id: str
    kind: str = Field(description="listing | site_config | meta")
    title: Optional[str] = None
    data: dict[str, Any] = Field(default_factory=dict)


class ContentPage(BaseModel):
    items: list[ContentItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 24
    cached: bool = False

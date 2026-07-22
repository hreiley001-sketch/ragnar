"""Models package — SQLModel tables + Birdman Pydantic conceptual map.

``from app.models import User`` keeps working (tables).
Pydantic API shapes live alongside: PublicUser, ContentPage, ActionRequest…
"""
from __future__ import annotations

from .actions import ActionRequest, ActionResult
from .content import ContentItem, ContentPage
from .tables import *  # noqa: F403
from .user import PublicUser, UserProfile

__all__ = [
    "ActionRequest",
    "ActionResult",
    "ContentItem",
    "ContentPage",
    "PublicUser",
    "UserProfile",
]

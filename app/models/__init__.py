"""Models package — SQLModel tables + Birdman Pydantic conceptual map.

``from app.models import User`` keeps working (tables).
Pydantic API + Supabase shapes live alongside.
"""
from __future__ import annotations

from .actions import ActionRequest, ActionResult, BirdmanAction
from .content import BirdmanContent, ContentItem, ContentPage
from .marketplace import (
    CardCreate,
    CardRead,
    ListingCreate,
    ListingPage,
    ListingRead,
    MarketEventPage,
    MarketEventRead,
    OrderCreate,
    OrderRead,
    OrderStatusUpdate,
    SellerOnboard,
)
from .realtime import BirdmanRealtimeEvent, RealtimePulse
from .system_log import BirdmanSystemLog
from .tables import *  # noqa: F403
from .user import BirdmanUser, PublicUser, UserProfile

__all__ = [
    "ActionRequest",
    "ActionResult",
    "BirdmanAction",
    "BirdmanContent",
    "BirdmanRealtimeEvent",
    "BirdmanSystemLog",
    "BirdmanUser",
    "CardCreate",
    "CardRead",
    "ContentItem",
    "ContentPage",
    "ListingCreate",
    "ListingPage",
    "ListingRead",
    "MarketEventPage",
    "MarketEventRead",
    "OrderCreate",
    "OrderRead",
    "OrderStatusUpdate",
    "PublicUser",
    "RealtimePulse",
    "SellerOnboard",
    "UserProfile",
]

"""User-shaped models — API surface + Supabase ``users`` row shape."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PublicUser(BaseModel):
    """Legacy marketplace session user (integer PK) — storefront path."""

    id: int
    email: str
    name: Optional[str] = None
    role: str = "user"
    seller_handle: Optional[str] = None
    email_verified: bool = False


class UserProfile(BaseModel):
    user: Optional[PublicUser] = None
    auth: str = Field(description="cookie | bearer | anonymous")
    supabase_linked: bool = False


class BirdmanUser(BaseModel):
    """Supabase ``public.users`` — PK matches auth.users.id."""

    id: UUID
    email: str
    username: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    profile_data: dict[str, Any] = Field(default_factory=dict)

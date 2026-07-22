"""User-shaped API models (conceptual — not SQLModel tables)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class PublicUser(BaseModel):
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

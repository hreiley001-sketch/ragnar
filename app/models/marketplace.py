"""Marketplace pydantic shapes — cards · listings · orders · market_events."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CardCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    set_name: Optional[str] = Field(default=None, max_length=120)
    year: Optional[int] = Field(default=None, ge=1900, le=2100)
    grade: Optional[str] = Field(default=None, max_length=40)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CardRead(BaseModel):
    id: UUID
    owner_id: UUID
    name: str
    set_name: Optional[str] = None
    year: Optional[int] = None
    grade: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    persisted: bool = True


class ListingCreate(BaseModel):
    card_id: UUID
    price: Decimal = Field(gt=0)
    status: Literal["active", "sold", "cancelled"] = "active"


class ListingRead(BaseModel):
    id: UUID
    card_id: UUID
    seller_id: UUID
    price: Decimal
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    persisted: bool = True


class ListingPage(BaseModel):
    items: list[ListingRead] = Field(default_factory=list)
    total: int = 0
    cached: bool = False


class OrderCreate(BaseModel):
    listing_id: UUID


class OrderRead(BaseModel):
    id: UUID
    buyer_id: UUID
    listing_id: UUID
    status: str
    total: Decimal
    created_at: Optional[datetime] = None
    persisted: bool = True


class OrderStatusUpdate(BaseModel):
    status: Literal["pending", "paid", "shipped", "completed", "cancelled"]


class MarketEventRead(BaseModel):
    id: UUID
    type: str
    user_id: Optional[UUID] = None
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None


class MarketEventPage(BaseModel):
    items: list[MarketEventRead] = Field(default_factory=list)
    total: int = 0
    cached: bool = False


class SellerOnboard(BaseModel):
    username: Optional[str] = Field(default=None, max_length=40)
    profile_data: dict[str, Any] = Field(default_factory=dict)

"""Request/response schemas for the API (separate from the DB table model)."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from .models import Category, Condition, GradingCompany, Listing


class SortOption(str, Enum):
    newest = "newest"
    price_asc = "price_asc"
    price_desc = "price_desc"
    grade_desc = "grade_desc"


class ListingCreate(BaseModel):
    title: str = Field(min_length=2, max_length=140)
    category: Category
    set_name: Optional[str] = Field(default=None, max_length=120)
    card_number: Optional[str] = Field(default=None, max_length=40)
    player_or_character: Optional[str] = Field(default=None, max_length=120)
    year: Optional[int] = Field(default=None, ge=1900, le=2100)

    is_graded: bool = False
    condition: Optional[Condition] = None
    grading_company: Optional[GradingCompany] = None
    grade: Optional[float] = Field(default=None, ge=1, le=10)

    price: float = Field(gt=0, le=1_000_000, description="Price in dollars")
    quantity: int = Field(default=1, ge=1, le=100_000)
    image_url: Optional[str] = Field(default=None, max_length=500)
    description: Optional[str] = Field(default=None, max_length=2000)

    # Either a display name, a seller handle, or both. If a handle resolves to a
    # known seller, the server treats that seller record as the source of truth
    # (including Founding status).
    seller_name: Optional[str] = Field(default=None, min_length=2, max_length=80)
    seller_handle: Optional[str] = Field(default=None, max_length=40)
    is_founding_seller: bool = False

    @model_validator(mode="after")
    def _check_condition_or_grade(self) -> "ListingCreate":
        if self.is_graded:
            if not self.grading_company or self.grade is None:
                raise ValueError(
                    "Graded cards require both 'grading_company' and 'grade'."
                )
        else:
            if not self.condition:
                raise ValueError(
                    "Raw (ungraded) cards require a 'condition'."
                )
        if not self.seller_name and not self.seller_handle:
            raise ValueError("Provide 'seller_name' or 'seller_handle'.")
        return self


class ListingRead(BaseModel):
    id: int
    title: str
    category: str
    set_name: Optional[str]
    card_number: Optional[str]
    player_or_character: Optional[str]
    year: Optional[int]
    is_graded: bool
    condition: Optional[str]
    grading_company: Optional[str]
    grade: Optional[float]
    price: float
    price_cents: int
    quantity: int
    image_url: Optional[str]
    description: Optional[str]
    seller_name: str
    is_founding_seller: bool
    status: str
    created_at: datetime

    @classmethod
    def from_listing(cls, listing: Listing) -> "ListingRead":
        return cls(
            id=listing.id,
            title=listing.title,
            category=listing.category,
            set_name=listing.set_name,
            card_number=listing.card_number,
            player_or_character=listing.player_or_character,
            year=listing.year,
            is_graded=listing.is_graded,
            condition=listing.condition,
            grading_company=listing.grading_company,
            grade=listing.grade,
            price=round(listing.price_cents / 100, 2),
            price_cents=listing.price_cents,
            quantity=listing.quantity,
            image_url=listing.image_url,
            description=listing.description,
            seller_name=listing.seller_name,
            is_founding_seller=listing.is_founding_seller,
            status=listing.status,
            created_at=listing.created_at,
        )


class ListingPage(BaseModel):
    items: list[ListingRead]
    total: int
    page: int
    page_size: int
    pages: int


# --------------------------- sellers --------------------------- #

class SellerApply(BaseModel):
    handle: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: str = Field(min_length=2, max_length=80)
    email: Optional[str] = Field(default=None, max_length=160)
    apply_for_founding: bool = True


class SellerState(BaseModel):
    handle: str
    display_name: str
    is_founding: bool
    founding_number: Optional[int]
    intro_active: bool
    intro_ends_at: Optional[datetime]
    intro_days_left: Optional[int]
    intro_sales_remaining: Optional[float]
    effective_rate: float


class FoundingStatus(BaseModel):
    claimed: int
    cap: int
    remaining: int
    intro_days: int
    intro_sales_cap: float


# --------------------------- sales / comps --------------------------- #

class MarkSold(BaseModel):
    price: Optional[float] = Field(
        default=None, gt=0, le=1_000_000,
        description="Sale price in dollars; defaults to the listing price.",
    )


class SaleRecent(BaseModel):
    price: float
    sold_at: datetime
    grading_company: Optional[str] = None
    grade: Optional[float] = None
    condition: Optional[str] = None
    source: str


class SalesHistory(BaseModel):
    count: int
    average: Optional[float]
    median: Optional[float]
    low: Optional[float]
    high: Optional[float]
    last_price: Optional[float]
    last_sold_at: Optional[datetime]
    suggested_price: Optional[float]
    series: list[dict]
    recent: list[SaleRecent]


# --------------------------- scan --------------------------- #

class ScanFields(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    set_name: Optional[str] = None
    card_number: Optional[str] = None
    player_or_character: Optional[str] = None
    year: Optional[int] = None
    is_graded: bool = False
    condition: Optional[str] = None
    grading_company: Optional[str] = None
    grade: Optional[float] = None


class MarketPrice(BaseModel):
    matched_name: Optional[str] = None
    set: Optional[str] = None
    number: Optional[str] = None
    rarity: Optional[str] = None
    market: Optional[float] = None
    low: Optional[float] = None
    foil: Optional[float] = None
    change_7d: Optional[float] = None
    listings: Optional[int] = None
    source: str


class ScanResponse(BaseModel):
    image_url: str
    provider: str
    confidence: float
    notes: str
    fields: ScanFields
    sales_history: SalesHistory
    market_price: Optional[MarketPrice] = None

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
    shipping: float = Field(default=0, ge=0, le=10_000, description="Shipping in dollars")
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
    shipping: float = 0
    is_featured: bool = False
    view_count: int = 0
    quantity: int
    image_url: Optional[str]
    # Optimized delivery URLs (Cloudinary WebP/auto-quality). Equal to image_url
    # when the media CDN isn't configured, so the frontend can always use them.
    thumb_url: Optional[str] = None
    image_optimized: Optional[str] = None
    image_enhanced: bool = False
    description: Optional[str]
    seller_name: str
    is_founding_seller: bool
    status: str
    created_at: datetime

    @classmethod
    def from_listing(cls, listing: Listing) -> "ListingRead":
        from .media import cdn_url, thumb_url  # lazy: avoids import cycles
        img = listing.image_url
        pid = listing.image_public_id
        return cls(
            shipping=round((listing.shipping_cents or 0) / 100, 2),
            is_featured=bool(listing.is_featured),
            view_count=listing.view_count or 0,
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
            image_url=img,
            thumb_url=(thumb_url(img, pid) if img or pid else None),
            image_optimized=(cdn_url(img, public_id=pid) if img or pid else None),
            image_enhanced=bool(getattr(listing, "image_enhanced", False)),
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


# --------------------------- stores --------------------------- #

class StoreSummary(BaseModel):
    handle: str
    display_name: str
    tagline: Optional[str] = None
    avatar_url: Optional[str] = None
    banner_url: Optional[str] = None
    avatar_optimized: Optional[str] = None
    banner_optimized: Optional[str] = None
    accent_color: Optional[str] = None
    font_family: Optional[str] = None
    is_founding: bool = False
    founding_number: Optional[int] = None
    listing_count: int = 0
    is_live: bool = False


class StoreProfile(StoreSummary):
    bio: Optional[str] = None


class StoreUpdate(BaseModel):
    tagline: Optional[str] = Field(default=None, max_length=140)
    bio: Optional[str] = Field(default=None, max_length=1000)
    banner_url: Optional[str] = Field(default=None, max_length=500)
    avatar_url: Optional[str] = Field(default=None, max_length=500)
    accent_color: Optional[str] = Field(default=None, max_length=16)
    font_family: Optional[str] = Field(default=None, max_length=80)
    store_public: Optional[bool] = None


class SellerApplyResult(SellerState):
    store_edit_token: Optional[str] = None


# --------------------------- founding applications --------------------------- #

class FoundingApplicationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=160)
    handle_wanted: Optional[str] = Field(default=None, max_length=40)
    categories: Optional[str] = Field(default=None, max_length=300)
    current_platforms: Optional[str] = Field(default=None, max_length=300)
    monthly_volume: Optional[str] = Field(default=None, max_length=80)
    message: Optional[str] = Field(default=None, max_length=2000)


class FoundingApplicationRead(BaseModel):
    id: int
    name: str
    email: str
    handle_wanted: Optional[str]
    categories: Optional[str]
    current_platforms: Optional[str]
    monthly_volume: Optional[str]
    message: Optional[str]
    status: str
    created_at: datetime


# --------------------------- live streams --------------------------- #

class LiveStreamCreate(BaseModel):
    title: str = Field(min_length=2, max_length=140)
    embed_url: Optional[str] = Field(default=None, max_length=500)
    thumbnail_url: Optional[str] = Field(default=None, max_length=500)
    scheduled_at: Optional[datetime] = None
    status: Optional[str] = Field(default="scheduled")


class LiveStreamUpdate(BaseModel):
    status: Optional[str] = None
    embed_url: Optional[str] = Field(default=None, max_length=500)
    viewer_count: Optional[int] = None


class LiveStreamRead(BaseModel):
    id: int
    seller_handle: str
    seller_name: str
    avatar_url: Optional[str] = None
    accent_color: Optional[str] = None
    title: str
    status: str
    embed_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    viewer_count: int = 0


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

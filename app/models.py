"""Database models and the structured taxonomy that makes RAGNAR listings
searchable in the way TCGplayer/eBay listings often aren't.

Enum *values* are stored as plain strings in the columns (simple, portable,
easy to filter with LIKE); the API layer validates incoming values against
these same enums, so we get structure without SQLAlchemy enum-column quirks.

Money is stored as integer cents to avoid floating-point drift.
Timestamps are naive UTC so comparisons stay consistent across SQLite round-trips.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    """Naive UTC 'now' (no tzinfo) — matches what SQLite returns on read."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Category(str, Enum):
    """The card verticals RAGNAR supports. Launch focuses on a single wedge,
    but the platform is modelled for the full set."""

    pokemon = "Pokémon"
    magic = "Magic: The Gathering"
    yugioh = "Yu-Gi-Oh!"
    one_piece = "One Piece"
    lorcana = "Disney Lorcana"
    basketball = "Sports — Basketball"
    baseball = "Sports — Baseball"
    football = "Sports — Football"
    soccer = "Sports — Soccer"
    other = "Other"


class Condition(str, Enum):
    """Raw (ungraded) card condition, using the hobby-standard ladder."""

    near_mint = "Near Mint"
    lightly_played = "Lightly Played"
    moderately_played = "Moderately Played"
    heavily_played = "Heavily Played"
    damaged = "Damaged"


class GradingCompany(str, Enum):
    psa = "PSA"
    bgs = "BGS"
    sgc = "SGC"
    cgc = "CGC"
    tag = "TAG"
    other = "Other"


class ListingStatus(str, Enum):
    active = "active"
    sold = "sold"
    draft = "draft"


class UserRole(str, Enum):
    user = "user"
    admin = "admin"  # staff / Command Hub access


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True, max_length=160)
    name: Optional[str] = Field(default=None, max_length=120)
    password_hash: Optional[str] = Field(default=None, max_length=255)  # null for Google-only
    google_sub: Optional[str] = Field(default=None, index=True, max_length=64)
    email_verified: bool = Field(default=False)
    verify_token: Optional[str] = Field(default=None, index=True, max_length=64)
    verify_sent_at: Optional[datetime] = Field(default=None)
    role: str = Field(default=UserRole.user.value, index=True)
    seller_handle: Optional[str] = Field(default=None, index=True, max_length=40)
    marketing_opt_in: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utcnow, index=True)


class UserSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    token: str = Field(index=True, unique=True, max_length=64)
    user_id: int = Field(foreign_key="user.id", index=True)
    expires_at: datetime = Field(index=True)
    created_at: datetime = Field(default_factory=utcnow)


class Seller(SQLModel, table=True):
    """A seller account. Founding Sellers get the 0% intro window and permanent
    4% rate; everyone else is on the standard rate."""

    id: Optional[int] = Field(default=None, primary_key=True)
    handle: str = Field(index=True, unique=True, max_length=40)
    display_name: str = Field(max_length=80)
    email: Optional[str] = Field(default=None, max_length=160)

    is_founding: bool = Field(default=False, index=True)
    founding_number: Optional[int] = Field(default=None, index=True)  # 1..cap
    founding_activated_at: Optional[datetime] = Field(default=None)
    founding_intro_ends_at: Optional[datetime] = Field(default=None)
    # Sales accrued during the 0% intro window, to enforce the $ cap.
    founding_intro_sales_cents: int = Field(default=0)

    # Stripe Connect (Express) — seller's connected account for payouts.
    stripe_account_id: Optional[str] = Field(default=None, index=True)
    stripe_charges_enabled: bool = Field(default=False)

    # --- Storefront customization (the seller's "own little store") ---
    tagline: Optional[str] = Field(default=None, max_length=140)
    bio: Optional[str] = Field(default=None, max_length=1000)
    banner_url: Optional[str] = Field(default=None, max_length=500)
    avatar_url: Optional[str] = Field(default=None, max_length=500)
    accent_color: Optional[str] = Field(default=None, max_length=16)  # hex, e.g. #6fd6ff
    font_family: Optional[str] = Field(default=None, max_length=80)  # Google Font family
    store_public: bool = Field(default=True, index=True)
    # Secret the seller uses to edit their own store (returned once on signup).
    store_edit_token: Optional[str] = Field(default=None, index=True)

    created_at: datetime = Field(default_factory=utcnow, index=True)


class LiveStream(SQLModel, table=True):
    """A live (or scheduled) selling stream for a seller's store.

    ``embed_url`` is where a real video provider (Mux/LiveKit/YouTube/etc.) plugs
    in later; until then a stream can still be listed/scheduled.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    seller_id: int = Field(foreign_key="seller.id", index=True)
    title: str = Field(max_length=140)
    status: str = Field(default="scheduled", index=True)  # scheduled | live | ended
    embed_url: Optional[str] = Field(default=None, max_length=500)
    thumbnail_url: Optional[str] = Field(default=None, max_length=500)
    scheduled_at: Optional[datetime] = Field(default=None)
    started_at: Optional[datetime] = Field(default=None)
    viewer_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=utcnow, index=True)


class Listing(SQLModel, table=True):
    """A single card for sale."""

    id: Optional[int] = Field(default=None, primary_key=True)

    # What it is
    title: str = Field(index=True, max_length=140)
    category: str = Field(index=True)
    set_name: Optional[str] = Field(default=None, index=True, max_length=120)
    card_number: Optional[str] = Field(default=None, max_length=40)
    player_or_character: Optional[str] = Field(default=None, index=True, max_length=120)
    year: Optional[int] = Field(default=None)

    # Condition / grading (a card is either graded OR has a raw condition)
    is_graded: bool = Field(default=False, index=True)
    condition: Optional[str] = Field(default=None, index=True)
    grading_company: Optional[str] = Field(default=None, index=True)
    grade: Optional[float] = Field(default=None, index=True)

    # Commerce
    price_cents: int = Field(index=True)
    quantity: int = Field(default=1)
    shipping_cents: int = Field(default=0)
    is_featured: bool = Field(default=False, index=True)
    view_count: int = Field(default=0)
    image_url: Optional[str] = Field(default=None, max_length=500)
    image_public_id: Optional[str] = Field(default=None, max_length=200)  # Cloudinary id
    image_enhanced: bool = Field(default=False)  # AI-upscaled/cleaned
    description: Optional[str] = Field(default=None, max_length=2000)

    # Who's selling
    seller_id: Optional[int] = Field(default=None, foreign_key="seller.id", index=True)
    seller_name: str = Field(index=True, max_length=80)
    is_founding_seller: bool = Field(default=False, index=True)

    status: str = Field(default=ListingStatus.active.value, index=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow)


# --------------------------------------------------------------------------- #
# Commerce parity: orders, offers, watchlists, feedback, disputes
# --------------------------------------------------------------------------- #


class OrderStatus(str, Enum):
    pending = "pending"        # awaiting payment (e.g. accepted offer, no Stripe)
    paid = "paid"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"
    disputed = "disputed"


class Order(SQLModel, table=True):
    """A purchase — the record buyers and sellers manage after checkout."""

    id: Optional[int] = Field(default=None, primary_key=True)
    listing_id: Optional[int] = Field(default=None, foreign_key="listing.id", index=True)
    seller_id: Optional[int] = Field(default=None, foreign_key="seller.id", index=True)
    buyer_user_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    buyer_name: Optional[str] = Field(default=None, max_length=120)
    buyer_email: Optional[str] = Field(default=None, max_length=160)

    title: str = Field(max_length=160)  # denormalized so history survives deletes
    price_cents: int = Field(default=0)
    shipping_cents: int = Field(default=0)
    status: str = Field(default=OrderStatus.paid.value, index=True)
    tracking_number: Optional[str] = Field(default=None, max_length=80)
    carrier: Optional[str] = Field(default=None, max_length=40)
    stripe_session_id: Optional[str] = Field(default=None, index=True, max_length=120)
    source: str = Field(default="manual")  # stripe | offer | manual | ride
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow)


class OfferStatus(str, Enum):
    open = "open"
    countered = "countered"
    accepted = "accepted"
    declined = "declined"
    withdrawn = "withdrawn"


class Offer(SQLModel, table=True):
    """eBay-style Best Offer negotiation on a listing."""

    id: Optional[int] = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="listing.id", index=True)
    seller_id: Optional[int] = Field(default=None, foreign_key="seller.id", index=True)
    buyer_user_id: int = Field(foreign_key="user.id", index=True)
    amount_cents: int
    message: Optional[str] = Field(default=None, max_length=500)
    counter_amount_cents: Optional[int] = Field(default=None)
    status: str = Field(default=OfferStatus.open.value, index=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow)


class WatchItem(SQLModel, table=True):
    """Watchlist — a user keeping an eye on a listing."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    listing_id: int = Field(foreign_key="listing.id", index=True)
    created_at: datetime = Field(default_factory=utcnow)


class SavedSearch(SQLModel, table=True):
    """Saved search — alerts the user when a new listing matches."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str = Field(max_length=80)
    # Stored filters: {q, category, graded, grading_company, min_grade, min_price, max_price}
    filters: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)


class Feedback(SQLModel, table=True):
    """Buyer feedback on a completed order (seller ratings)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="order.id", index=True, unique=True)
    seller_id: int = Field(foreign_key="seller.id", index=True)
    rater_user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    stars: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=1000)
    created_at: datetime = Field(default_factory=utcnow, index=True)


class Dispute(SQLModel, table=True):
    """Buyer-protection dispute on an order."""

    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="order.id", index=True)
    opened_by_user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    reason: str = Field(max_length=1000)
    status: str = Field(default="open", index=True)  # open | resolved_refund | resolved_denied
    resolution: Optional[str] = Field(default=None, max_length=1000)
    created_at: datetime = Field(default_factory=utcnow, index=True)
    resolved_at: Optional[datetime] = Field(default=None)


# --------------------------------------------------------------------------- #
# Social: follows, messages, want lists, notifications
# --------------------------------------------------------------------------- #


class Follow(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    seller_id: int = Field(foreign_key="seller.id", index=True)
    created_at: datetime = Field(default_factory=utcnow)


class Conversation(SQLModel, table=True):
    """A message thread between a user (buyer) and a seller (store)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    seller_id: int = Field(foreign_key="seller.id", index=True)
    listing_id: Optional[int] = Field(default=None, foreign_key="listing.id")
    updated_at: datetime = Field(default_factory=utcnow, index=True)
    created_at: datetime = Field(default_factory=utcnow)


class ChatMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="conversation.id", index=True)
    sender: str = Field(max_length=10)  # "user" | "seller"
    body: str = Field(max_length=2000)
    read: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)


class WantItem(SQLModel, table=True):
    """Want list — 'looking for' posts sellers can browse and fulfill."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    description: str = Field(max_length=300)
    category: Optional[str] = Field(default=None, index=True)
    max_price_cents: Optional[int] = Field(default=None)
    status: str = Field(default="open", index=True)  # open | fulfilled | closed
    created_at: datetime = Field(default_factory=utcnow, index=True)


class Notification(SQLModel, table=True):
    """In-app notification (the bell)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    type: str = Field(index=True)
    title: str = Field(max_length=200)
    body: Optional[str] = Field(default=None, max_length=500)
    link: Optional[str] = Field(default=None, max_length=300)
    read: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)


# --------------------------------------------------------------------------- #
# Whatnot parity: giveaways (ride chat rides on RideEvent)
# --------------------------------------------------------------------------- #


class Giveaway(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ride_id: int = Field(foreign_key="ride.id", index=True)
    title: str = Field(max_length=140)
    status: str = Field(default="open", index=True)  # open | drawn | cancelled
    winner: Optional[str] = Field(default=None, max_length=80)
    created_at: datetime = Field(default_factory=utcnow, index=True)


class GiveawayEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    giveaway_id: int = Field(foreign_key="giveaway.id", index=True)
    name: str = Field(max_length=80)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=utcnow)


class FoundingApplication(SQLModel, table=True):
    """A prospective seller's application to join the Founding 250.

    Applications are reviewed (not auto-approved) — 'apply, not open signup', per
    the launch plan. Approving one creates a founding Seller.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=120)
    email: str = Field(index=True, max_length=160)
    handle_wanted: Optional[str] = Field(default=None, max_length=40)
    categories: Optional[str] = Field(default=None, max_length=300)  # what they sell
    current_platforms: Optional[str] = Field(default=None, max_length=300)  # eBay/TCGplayer links
    monthly_volume: Optional[str] = Field(default=None, max_length=80)
    message: Optional[str] = Field(default=None, max_length=2000)
    status: str = Field(default="pending", index=True)  # pending | approved | rejected
    created_at: datetime = Field(default_factory=utcnow, index=True)


class RideStatus(str, Enum):
    idle = "idle"
    lobby = "lobby"
    showcase = "showcase"
    bidding = "bidding"
    cooldown = "cooldown"
    archived = "archived"


class Ride(SQLModel, table=True):
    """A BirdmanOS 'rollercoaster' — a structured live experience (auction).

    The state machine runs idle → lobby → showcase → bidding → cooldown → archived.
    ``phases`` and ``apis`` are stored as JSON so a ride is fully data-defined.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    type: str = Field(default="auction", index=True)
    title: str = Field(max_length=160)
    seller_id: Optional[int] = Field(default=None, foreign_key="seller.id", index=True)
    listing_id: Optional[int] = Field(default=None, foreign_key="listing.id")

    status: str = Field(default=RideStatus.idle.value, index=True)
    phases: list = Field(default_factory=list, sa_column=Column(JSON))  # [{name,duration_sec}]
    apis: dict = Field(default_factory=dict, sa_column=Column(JSON))
    phase_index: int = Field(default=-1)
    current_phase: Optional[str] = Field(default=None)
    phase_started_at: Optional[datetime] = Field(default=None)
    phase_ends_at: Optional[datetime] = Field(default=None)

    # Auction economics (cents)
    starting_bid_cents: int = Field(default=0)
    reserve_cents: int = Field(default=0)
    current_bid_cents: int = Field(default=0)
    current_bidder: Optional[str] = Field(default=None)
    winner: Optional[str] = Field(default=None)
    market_price_cents: Optional[int] = Field(default=None)  # from showcase pricing fetch

    viewer_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow)


class Bid(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ride_id: int = Field(foreign_key="ride.id", index=True)
    bidder: str = Field(max_length=80)
    bidder_user_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    amount_cents: int = Field(index=True)
    status: str = Field(default="placed")  # placed | outbid | won
    created_at: datetime = Field(default_factory=utcnow, index=True)


class RideEvent(SQLModel, table=True):
    """The BirdmanOS event bus, persisted. Command Hub + analytics read from here."""

    id: Optional[int] = Field(default=None, primary_key=True)
    ride_id: Optional[int] = Field(default=None, foreign_key="ride.id", index=True)
    type: str = Field(index=True)
    data: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow, index=True)


class Sale(SQLModel, table=True):
    """A completed sale — RAGNAR's own sold-price history (the honest comp set).

    Card identity is denormalized onto the row so history survives even if the
    original listing is deleted, and so seeded/external comps can be stored the
    same way.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    listing_id: Optional[int] = Field(default=None, foreign_key="listing.id", index=True)

    category: str = Field(index=True)
    set_name: Optional[str] = Field(default=None, index=True, max_length=120)
    card_number: Optional[str] = Field(default=None, index=True, max_length=40)
    player_or_character: Optional[str] = Field(default=None, index=True, max_length=120)
    is_graded: bool = Field(default=False, index=True)
    grading_company: Optional[str] = Field(default=None, index=True)
    grade: Optional[float] = Field(default=None, index=True)
    condition: Optional[str] = Field(default=None)

    sold_price_cents: int = Field(index=True)
    sold_at: datetime = Field(default_factory=utcnow, index=True)
    source: str = Field(default="ragnar", index=True)  # ragnar | seed | external


class SiteSetting(SQLModel, table=True):
    """Staff-editable site content (announcement bar, landing copy, community
    links). A key/value store gated by a whitelist registry (see site_config.py)
    so staff edit *content*, never code. Each edit records who made it."""

    key: str = Field(primary_key=True, max_length=64)
    value: str = Field(default="", max_length=4000)
    updated_by: Optional[str] = Field(default=None, max_length=160)
    updated_at: datetime = Field(default_factory=utcnow)

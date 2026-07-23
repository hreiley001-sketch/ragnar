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
    reset_token: Optional[str] = Field(default=None, index=True, max_length=64)
    reset_sent_at: Optional[datetime] = Field(default=None)
    pending_email: Optional[str] = Field(default=None, max_length=160)
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
    """A seller account. The first 250 sellers to sign up (Founding Sellers)
    get a flat 4% platform rate forever; everyone else pays the standard
    rate. No time window, no sales cap — just a permanent founders rate."""

    id: Optional[int] = Field(default=None, primary_key=True)
    handle: str = Field(index=True, unique=True, max_length=40)
    display_name: str = Field(max_length=80)
    email: Optional[str] = Field(default=None, max_length=160)

    is_founding: bool = Field(default=False, index=True)
    founding_number: Optional[int] = Field(default=None, index=True)  # 1..cap
    founding_activated_at: Optional[datetime] = Field(default=None)
    # Unused by the fee engine (no intro window/cap) — kept for schema back-compat.
    founding_intro_ends_at: Optional[datetime] = Field(default=None)
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


class LiveStreamReminder(SQLModel, table=True):
    """A user's 'notify me' subscription for a scheduled stream."""

    user_id: int = Field(foreign_key="user.id", primary_key=True)
    stream_id: int = Field(foreign_key="livestream.id", primary_key=True)
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
    refunded = "refunded"      # money returned via Stripe (or full ledger cancel for non-Stripe)


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
    stripe_refund_id: Optional[str] = Field(default=None, index=True, max_length=120)
    refunded_cents: int = Field(default=0)
    source: str = Field(default="manual")  # stripe | offer | manual | ride
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow)


class ProcessedStripeEvent(SQLModel, table=True):
    """Idempotency ledger for Stripe webhooks — event_id is unique."""

    event_id: str = Field(primary_key=True, max_length=120)
    event_type: str = Field(max_length=80)
    processed_at: datetime = Field(default_factory=utcnow, index=True)


class InventoryHold(SQLModel, table=True):
    """Temporary reservation created at Checkout Session creation.

    Available units = listing.quantity - active (unreleased, unconverted, unexpired) holds.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="listing.id", index=True)
    buyer_user_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    stripe_session_id: str = Field(index=True, unique=True, max_length=120)
    quantity: int = Field(default=1)
    expires_at: datetime = Field(index=True)
    released: bool = Field(default=False, index=True)
    converted: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=utcnow)


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


class SiteCollaborator(SQLModel, table=True):
    """Partner access for Site Builder controls in Command Hub.

    role:
    - owner: full site builder + collaborator management
    - editor: full site builder (theme + copy), no collaborator management
    - content: copy/content only, no look-and-feel edits
    """

    email: str = Field(primary_key=True, max_length=160)
    role: str = Field(default="editor", max_length=20, index=True)
    added_by: Optional[str] = Field(default=None, max_length=160)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


# --------------------------------------------------------------------------- #
# AI Support OS — conversations, knowledge, audit, human review queues
# --------------------------------------------------------------------------- #


class SupportChannel(str, Enum):
    web = "web"
    in_app = "in_app"
    email = "email"
    social = "social"
    sms = "sms"


class SupportCaseStatus(str, Enum):
    open = "open"
    awaiting_user = "awaiting_user"
    in_workflow = "in_workflow"
    pending_review = "pending_review"
    escalated = "escalated"
    resolved = "resolved"
    closed = "closed"


class SupportQueue(str, Enum):
    """Human review queues — AI routes here only for edge cases."""

    general = "general"
    legal = "legal"
    high_value = "high_value"
    chargeback = "chargeback"
    fraud = "fraud"


class SupportConversation(SQLModel, table=True):
    """A support thread owned by the AI Support OS (not seller DMs)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    public_id: str = Field(index=True, unique=True, max_length=32)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    channel: str = Field(default=SupportChannel.web.value, index=True, max_length=20)
    status: str = Field(default=SupportCaseStatus.open.value, index=True, max_length=32)
    intent: Optional[str] = Field(default=None, index=True, max_length=64)
    confidence: Optional[float] = Field(default=None)
    tone: str = Field(default="normal", max_length=24)  # normal | frustrated | high_risk
    queue: Optional[str] = Field(default=None, index=True, max_length=32)
    order_id: Optional[int] = Field(default=None, foreign_key="order.id", index=True)
    workflow: Optional[str] = Field(default=None, max_length=64)
    workflow_step: Optional[str] = Field(default=None, max_length=64)
    entities: dict = Field(default_factory=dict, sa_column=Column(JSON))
    context: dict = Field(default_factory=dict, sa_column=Column(JSON))
    resolved_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow, index=True)


class SupportMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="supportconversation.id", index=True)
    role: str = Field(max_length=16)  # user | assistant | system | human
    body: str = Field(max_length=4000)
    meta: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow, index=True)


class SupportAuditLog(SQLModel, table=True):
    """Immutable trail of AI decisions, policy refs, and actions taken."""

    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: Optional[int] = Field(
        default=None, foreign_key="supportconversation.id", index=True
    )
    user_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    order_id: Optional[int] = Field(default=None, foreign_key="order.id", index=True)
    actor: str = Field(default="ai", max_length=24)  # ai | human | system
    intent: Optional[str] = Field(default=None, max_length=64)
    decision: Optional[str] = Field(default=None, max_length=64)
    actions: list = Field(default_factory=list, sa_column=Column(JSON))
    policy_refs: list = Field(default_factory=list, sa_column=Column(JSON))
    confidence: Optional[float] = Field(default=None)
    risk: Optional[str] = Field(default=None, max_length=24)
    reason: Optional[str] = Field(default=None, max_length=2000)
    detail: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow, index=True)


class KnowledgeArticle(SQLModel, table=True):
    """Searchable marketplace policies, FAQs, seller rules, and playbooks."""

    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True, max_length=80)
    title: str = Field(max_length=160)
    category: str = Field(index=True, max_length=40)  # policy | faq | seller | playbook
    tags: list = Field(default_factory=list, sa_column=Column(JSON))
    body: str = Field(max_length=8000)
    # Machine-readable rules attached to the article (optional).
    rules: dict = Field(default_factory=dict, sa_column=Column(JSON))
    active: bool = Field(default=True, index=True)
    updated_at: datetime = Field(default_factory=utcnow)
    created_at: datetime = Field(default_factory=utcnow)


class SupportRefund(SQLModel, table=True):
    """Record of a refund (or store-credit) issued by AI or humans."""

    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="order.id", index=True)
    conversation_id: Optional[int] = Field(
        default=None, foreign_key="supportconversation.id", index=True
    )
    amount_cents: int = Field(default=0)
    kind: str = Field(default="full", max_length=24)  # full | partial | store_credit
    status: str = Field(default="recorded", index=True, max_length=32)
    # recorded | stripe_refunded | pending_review | denied
    stripe_refund_id: Optional[str] = Field(default=None, max_length=120)
    reason: Optional[str] = Field(default=None, max_length=500)
    issued_by: str = Field(default="ai", max_length=24)
    created_at: datetime = Field(default_factory=utcnow, index=True)


# --------------------------------------------------------------------------- #
# AI Shipping Agent (Dispatch) — quote → pack → label → track → exceptions
# --------------------------------------------------------------------------- #


class ShippingCaseStatus(str, Enum):
    open = "open"
    awaiting_user = "awaiting_user"
    in_workflow = "in_workflow"
    pending_review = "pending_review"
    escalated = "escalated"
    resolved = "resolved"
    closed = "closed"


class SellerShippingProfile(SQLModel, table=True):
    """Default ship-from address + prefs for a seller store."""

    id: Optional[int] = Field(default=None, primary_key=True)
    seller_id: int = Field(foreign_key="seller.id", index=True, unique=True)
    name: str = Field(default="", max_length=120)
    street1: str = Field(default="", max_length=120)
    city: str = Field(default="", max_length=80)
    state: str = Field(default="", max_length=40)
    zip: str = Field(default="", max_length=20)
    country: str = Field(default="US", max_length=2)
    phone: Optional[str] = Field(default=None, max_length=40)
    prefer: str = Field(default="balanced", max_length=20)  # cheapest | fastest | balanced
    updated_at: datetime = Field(default_factory=utcnow)
    created_at: datetime = Field(default_factory=utcnow)


class ShippingConversation(SQLModel, table=True):
    """Dispatch thread — seller-facing AI shipping agent."""

    id: Optional[int] = Field(default=None, primary_key=True)
    public_id: str = Field(index=True, unique=True, max_length=32)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    seller_id: Optional[int] = Field(default=None, foreign_key="seller.id", index=True)
    channel: str = Field(default="web", index=True, max_length=20)
    status: str = Field(default=ShippingCaseStatus.open.value, index=True, max_length=32)
    intent: Optional[str] = Field(default=None, index=True, max_length=64)
    confidence: Optional[float] = Field(default=None)
    tone: str = Field(default="normal", max_length=24)
    queue: Optional[str] = Field(default=None, index=True, max_length=32)
    order_id: Optional[int] = Field(default=None, foreign_key="order.id", index=True)
    workflow: Optional[str] = Field(default=None, max_length=64)
    workflow_step: Optional[str] = Field(default=None, max_length=64)
    entities: dict = Field(default_factory=dict, sa_column=Column(JSON))
    context: dict = Field(default_factory=dict, sa_column=Column(JSON))
    resolved_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow, index=True)


class ShippingMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="shippingconversation.id", index=True)
    role: str = Field(max_length=16)  # user | assistant | system | human
    body: str = Field(max_length=4000)
    meta: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow, index=True)


class ShippingAuditLog(SQLModel, table=True):
    """Immutable trail of Dispatch decisions and label actions."""

    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: Optional[int] = Field(
        default=None, foreign_key="shippingconversation.id", index=True
    )
    user_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    seller_id: Optional[int] = Field(default=None, foreign_key="seller.id", index=True)
    order_id: Optional[int] = Field(default=None, foreign_key="order.id", index=True)
    actor: str = Field(default="ai", max_length=24)
    intent: Optional[str] = Field(default=None, max_length=64)
    decision: Optional[str] = Field(default=None, max_length=64)
    actions: list = Field(default_factory=list, sa_column=Column(JSON))
    policy_refs: list = Field(default_factory=list, sa_column=Column(JSON))
    confidence: Optional[float] = Field(default=None)
    risk: Optional[str] = Field(default=None, max_length=24)
    reason: Optional[str] = Field(default=None, max_length=2000)
    detail: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow, index=True)


class ShippingLabel(SQLModel, table=True):
    """A purchased (or mock) shipping label tied to an order."""

    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: Optional[int] = Field(default=None, foreign_key="order.id", index=True)
    seller_id: Optional[int] = Field(default=None, foreign_key="seller.id", index=True)
    conversation_id: Optional[int] = Field(
        default=None, foreign_key="shippingconversation.id", index=True
    )
    label_id: str = Field(index=True, max_length=80)
    carrier: Optional[str] = Field(default=None, max_length=40)
    service: Optional[str] = Field(default=None, max_length=80)
    tracking_number: Optional[str] = Field(default=None, index=True, max_length=80)
    amount_cents: int = Field(default=0)
    currency: str = Field(default="USD", max_length=8)
    label_url: Optional[str] = Field(default=None, max_length=500)
    source: str = Field(default="mock", max_length=24)  # shippo | mock
    status: str = Field(default="created", index=True, max_length=32)
    # created | purchased | voided | used
    package_key: Optional[str] = Field(default=None, max_length=40)
    insurance_cents: int = Field(default=0)
    address_from: dict = Field(default_factory=dict, sa_column=Column(JSON))
    address_to: dict = Field(default_factory=dict, sa_column=Column(JSON))
    meta: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow, index=True)


# --------------------------------------------------------------------------- #
# Unified platform: social feed, groups, cart, collection
# --------------------------------------------------------------------------- #


class FeedPost(SQLModel, table=True):
    """Instagram-style seller post for the social feed."""

    id: Optional[int] = Field(default=None, primary_key=True)
    seller_id: int = Field(foreign_key="seller.id", index=True)
    kind: str = Field(default="post", index=True, max_length=32)
    # post | live_announce | pickup | pc_highlight | grading | spotlight | story
    title: Optional[str] = Field(default=None, max_length=200)
    body: str = Field(max_length=2000)
    image_url: Optional[str] = Field(default=None, max_length=500)
    listing_id: Optional[int] = Field(default=None, foreign_key="listing.id")
    tags: list = Field(default_factory=list, sa_column=Column(JSON))
    market_value_cents: Optional[int] = Field(default=None)
    like_count: int = Field(default=0)
    comment_count: int = Field(default=0)
    is_story: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)


class CommunityGroup(SQLModel, table=True):
    """Reddit-style collector group."""

    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True, max_length=60)
    name: str = Field(max_length=120)
    description: str = Field(default="", max_length=1000)
    kind: str = Field(default="club", index=True, max_length=40)
    # club | fantasy | meetup | seller_support | new
    banner_url: Optional[str] = Field(default=None, max_length=500)
    member_count: int = Field(default=0)
    created_by_user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=utcnow, index=True)


class GroupMember(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="communitygroup.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    role: str = Field(default="member", max_length=24)  # member | mod | admin
    created_at: datetime = Field(default_factory=utcnow)


class GroupThread(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="communitygroup.id", index=True)
    author_user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    title: str = Field(max_length=200)
    body: str = Field(max_length=4000)
    is_poll: bool = Field(default=False)
    poll_options: list = Field(default_factory=list, sa_column=Column(JSON))
    upvotes: int = Field(default=0)
    comment_count: int = Field(default=0)
    ai_summary: Optional[str] = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=utcnow, index=True)


class GroupComment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    thread_id: int = Field(foreign_key="groupthread.id", index=True)
    author_user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    body: str = Field(max_length=2000)
    upvotes: int = Field(default=0)
    created_at: datetime = Field(default_factory=utcnow, index=True)


class CartItem(SQLModel, table=True):
    """Multi-seller cart line (checkout still per-seller Stripe sessions)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    listing_id: int = Field(foreign_key="listing.id", index=True)
    quantity: int = Field(default=1)
    created_at: datetime = Field(default_factory=utcnow)


class CollectionItem(SQLModel, table=True):
    """Buyer collection — 'Add to collection' from listing pages."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    listing_id: Optional[int] = Field(default=None, foreign_key="listing.id")
    title: str = Field(max_length=200)
    notes: Optional[str] = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=utcnow, index=True)

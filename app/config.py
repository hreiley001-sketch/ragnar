"""Application configuration, sourced from environment variables.

Kept dependency-light on purpose (plain os.getenv + dotenv) so the MVP stays
easy to run anywhere — locally, in Docker, on Render, or on Azure.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _flag(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    # Identity
    app_name: str = "RAGNAR"
    version: str = "0.1.0"
    tagline: str = "Guided by counsel, driven by conquest."

    # Storage
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./ragnar.db")

    # CORS — comma separated. Default "*" for easy local dev; lock down in prod.
    allowed_origins: list[str] = [
        o.strip()
        for o in os.getenv("ALLOWED_ORIGINS", "*").split(",")
        if o.strip()
    ] or ["*"]

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()

    # --- Fee model (the core value proposition) ---
    # Standard platform take rate for everyone.
    standard_rate: float = float(os.getenv("RAGNAR_STANDARD_RATE", "0.05"))
    # Permanent thank-you rate for Founding Sellers (after their intro window).
    founding_rate: float = float(os.getenv("RAGNAR_FOUNDING_RATE", "0.04"))
    # Pass-through payment processing (Stripe-style).
    processing_rate: float = float(os.getenv("PROCESSING_RATE", "0.029"))
    processing_flat: float = float(os.getenv("PROCESSING_FLAT", "0.30"))

    # Estimated eBay fees, for the honest "you keep more here" comparison.
    # eBay trading-card final value fees land around 13.25% + a per-order fee.
    # Clearly an estimate; surfaced as such in the UI.
    ebay_rate: float = float(os.getenv("EBAY_FEE_RATE", "0.1325"))
    ebay_flat: float = float(os.getenv("EBAY_FLAT_FEE", "0.30"))

    # Founding 250 program
    founding_cap: int = int(os.getenv("FOUNDING_SELLER_CAP", "250"))
    founding_intro_days: int = int(os.getenv("FOUNDING_INTRO_DAYS", "90"))
    founding_intro_sales_cap: float = float(os.getenv("FOUNDING_INTRO_SALES_CAP", "2500"))

    # --- Uploads (scan-to-post photos) ---
    upload_dir: str = os.getenv("UPLOAD_DIR", "uploads")
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "12"))

    # --- Scan / card recognition ---
    # Provider for photo -> structured card fields.
    #   "auto"     : Ximilar if token set, else OpenAI vision if key set, else heuristic
    #   "ximilar"  : force Ximilar collectibles recognition
    #   "openai"   : force OpenAI vision
    #   "heuristic"/"none": filename + text heuristics only
    scan_provider: str = os.getenv("SCAN_PROVIDER", "auto").lower()
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "").strip()
    openai_vision_model: str = os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini")

    # Ximilar (https://docs.ximilar.com/collectibles/recognition)
    ximilar_token: str = os.getenv("XIMILAR_TOKEN", "").strip()
    ximilar_base: str = os.getenv(
        "XIMILAR_BASE", "https://api.ximilar.com/tagging/collectibles/v2"
    ).rstrip("/")
    # tcg_id | sport_id | slab_id
    ximilar_endpoint: str = os.getenv("XIMILAR_ENDPOINT", "tcg_id").strip()

    # --- Live pricing: TCG API (https://tcgapi.dev) ---
    tcg_api_base: str = os.getenv("TCG_API_BASE", "https://api.tcgapi.dev").rstrip("/")
    tcg_api_key: str = os.getenv("TCG_API_KEY", "").strip()

    # --- Sold comps / sales history ---
    # External comps provider. Defaults to the SoldComps shape; point the URL at
    # any provider that returns {items:[{soldPrice,endedAt,title,url,...}]}.
    comps_provider: str = os.getenv("COMPS_PROVIDER", "soldcomps").lower()
    comps_provider_url: str = os.getenv("COMPS_PROVIDER_URL", "").strip()
    comps_provider_key: str = os.getenv("COMPS_PROVIDER_KEY", "").strip()
    comps_auth_header: str = os.getenv("COMPS_AUTH_HEADER", "X-API-Key").strip()
    comps_lookback_days: int = int(os.getenv("COMPS_LOOKBACK_DAYS", "365"))

    # --- BirdmanOS rides (auction rollercoaster engine) ---
    ride_min_increment_cents: int = int(os.getenv("RIDE_MIN_INCREMENT_CENTS", "100"))
    ride_anti_snipe_seconds: int = int(os.getenv("RIDE_ANTI_SNIPE_SECONDS", "15"))
    ride_anti_snipe_extend_seconds: int = int(os.getenv("RIDE_ANTI_SNIPE_EXTEND_SECONDS", "20"))
    # Analytics observatory (PostHog) — event bus mirrors here when configured.
    posthog_api_key: str = os.getenv("POSTHOG_API_KEY", "").strip()
    posthog_host: str = os.getenv("POSTHOG_HOST", "https://us.i.posthog.com").rstrip("/")
    # Live-stream tunnel (LiveKit) — slot for real low-latency video later.
    livekit_url: str = os.getenv("LIVEKIT_URL", "").strip()
    livekit_api_key: str = os.getenv("LIVEKIT_API_KEY", "").strip()
    livekit_api_secret: str = os.getenv("LIVEKIT_API_SECRET", "").strip()

    # --- Email notifications (Resend) — key-gated ---
    resend_api_key: str = os.getenv("RESEND_API_KEY", "").strip()
    email_from: str = os.getenv("EMAIL_FROM", "RAGNAR <notifications@ragnarips.com>")

    # --- Discord webhook alerts (ops channel) — key-gated ---
    discord_webhook_url: str = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

    # --- Shipping (Shippo) — key-gated ---
    shippo_api_key: str = os.getenv("SHIPPO_API_KEY", "").strip()

    # --- PSA population/authentication (OAuth2; docs gated behind login) ---
    # Stub seam only — supply a pre-obtained access token to enable later.
    psa_access_token: str = os.getenv("PSA_ACCESS_TOKEN", "").strip()
    psa_base: str = os.getenv("PSA_BASE", "https://api.psacard.com/publicapi").rstrip("/")

    # --- Payments (Stripe Connect) ---
    stripe_secret_key: str = os.getenv("STRIPE_SECRET_KEY", "").strip()
    stripe_publishable_key: str = os.getenv("STRIPE_PUBLISHABLE_KEY", "").strip()
    stripe_webhook_secret: str = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
    platform_currency: str = os.getenv("PLATFORM_CURRENCY", "usd").lower()
    # Base URL used to build Stripe onboarding return + checkout success/cancel links.
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    payments_live: bool = _flag("PAYMENTS_LIVE", False)

    # --- SEO ---
    # Canonical site URL for sitemap/canonical/OG tags (falls back to base URL).
    site_url: str = os.getenv("SITE_URL", "").strip()
    seo_title: str = os.getenv("SEO_TITLE", "RAGNAR — Trading Card Marketplace")
    seo_description: str = os.getenv(
        "SEO_DESCRIPTION",
        "RAGNAR is a trust-first trading-card marketplace. Keep more of every sale, "
        "scan cards to list in seconds, and see real sold-price history. "
        "Apply to be one of 250 Founding Sellers.",
    )
    seo_keywords: str = os.getenv(
        "SEO_KEYWORDS",
        "trading card marketplace, sell trading cards, Pokemon cards, PSA graded cards, "
        "sports cards, buy sell trading cards, TCG marketplace, card sold prices, "
        "founding sellers, Magic the Gathering, Yu-Gi-Oh, One Piece cards",
    )

    # Keyword/SEO research providers (admin tools) — key-gated.
    serper_api_key: str = os.getenv("SERPER_API_KEY", "").strip()
    dataforseo_login: str = os.getenv("DATAFORSEO_LOGIN", "").strip()
    dataforseo_password: str = os.getenv("DATAFORSEO_PASSWORD", "").strip()

    # --- Accounts / auth ---
    session_cookie: str = os.getenv("SESSION_COOKIE", "ragnar_session")
    session_ttl_days: int = int(os.getenv("SESSION_TTL_DAYS", "30"))
    # Verified Google emails on this domain get staff (Command Hub) access.
    staff_email_domain: str = os.getenv("STAFF_EMAIL_DOMAIN", "ragnarips.com").lower().strip()
    admin_emails: list[str] = [
        e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()
    ]
    # Sign in with Google (OAuth) — key-gated. Create a client in Google Cloud.
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()

    # --- Admin command hub ---
    # Admin endpoints require X-Admin-Token == this value OR a signed-in staff
    # user. If neither is set/available, admin is disabled.
    admin_token: str = os.getenv("ADMIN_TOKEN", "").strip()

    # --- Media pipeline: Cloudinary (transform-CDN + AI background removal) ---
    # Key-gated. Without keys, media helpers return the original image untouched.
    cloudinary_cloud_name: str = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
    cloudinary_api_key: str = os.getenv("CLOUDINARY_API_KEY", "").strip()
    cloudinary_api_secret: str = os.getenv("CLOUDINARY_API_SECRET", "").strip()
    cloudinary_folder: str = os.getenv("CLOUDINARY_FOLDER", "ragnar").strip()

    # Dedicated background removal (Remove.bg) — key-gated fallback / standalone.
    removebg_api_key: str = os.getenv("REMOVEBG_API_KEY", "").strip()

    # AI image enhancement (Replicate) — key-gated; upscale/restore card photos.
    replicate_api_token: str = os.getenv("REPLICATE_API_TOKEN", "").strip()
    # Model run via the model-based predictions endpoint (no version hash needed).
    replicate_upscale_model: str = os.getenv(
        "REPLICATE_UPSCALE_MODEL", "nightmareai/real-esrgan"
    ).strip()
    replicate_upscale: int = int(os.getenv("REPLICATE_UPSCALE_FACTOR", "2"))

    # Web extraction (Firecrawl) — key-gated; scrape a card page -> price JSON.
    firecrawl_api_key: str = os.getenv("FIRECRAWL_API_KEY", "").strip()
    firecrawl_base: str = os.getenv("FIRECRAWL_BASE", "https://api.firecrawl.dev").rstrip("/")

    # Google Fonts metadata (per-store typography picker) — key-gated (has fallback).
    google_fonts_api_key: str = os.getenv("GOOGLE_FONTS_API_KEY", "").strip()

    # --- Free card catalogs ---
    # Scryfall (MTG) needs no key. Pokémon TCG works without a key; a key raises
    # rate limits.
    pokemontcg_key: str = os.getenv("POKEMONTCG_API_KEY", "").strip()
    catalog_user_agent: str = os.getenv("CATALOG_USER_AGENT", "Ragnar/0.1 (+https://ragnarips.com)")

    # Seed demo data (fake listings/sellers/streams) only when explicitly enabled.
    # Off by default so production stays clean.
    seed_demo: bool = _flag("SEED_DEMO", False)

    # --- AI Support OS governance thresholds ---
    # > support_conf_autonomous + low risk → AI resolves alone
    # support_conf_review .. autonomous or medium risk → act + flag for review
    # < support_conf_review or high risk → human queue
    support_conf_autonomous: float = float(os.getenv("SUPPORT_CONF_AUTONOMOUS", "0.90"))
    support_conf_review: float = float(os.getenv("SUPPORT_CONF_REVIEW", "0.70"))
    support_ai_max_refund_cents: int = int(os.getenv("SUPPORT_AI_MAX_REFUND_CENTS", "50000"))

    debug: bool = _flag("DEBUG", False)

    @property
    def founding_intro_sales_cap_cents(self) -> int:
        return int(self.founding_intro_sales_cap * 100)


settings = Settings()

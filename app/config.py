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

    # --- Admin command hub ---
    # Admin endpoints require X-Admin-Token == this value. If unset, admin is
    # disabled (endpoints return 503) — set a strong secret in production.
    admin_token: str = os.getenv("ADMIN_TOKEN", "").strip()

    # --- Free card catalogs ---
    # Scryfall (MTG) needs no key. Pokémon TCG works without a key; a key raises
    # rate limits.
    pokemontcg_key: str = os.getenv("POKEMONTCG_API_KEY", "").strip()
    catalog_user_agent: str = os.getenv("CATALOG_USER_AGENT", "Ragnar/0.1 (+https://ragnarips.com)")

    # Seed demo data (fake listings/sellers/streams) only when explicitly enabled.
    # Off by default so production stays clean.
    seed_demo: bool = _flag("SEED_DEMO", False)

    debug: bool = _flag("DEBUG", False)

    @property
    def founding_intro_sales_cap_cents(self) -> int:
        return int(self.founding_intro_sales_cap * 100)


settings = Settings()

"""RAGNAR marketplace — FastAPI application entrypoint.

Run locally:  uvicorn app.main:app --reload
Then open:    http://127.0.0.1:8000
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import init_db
from .routers import (
    admin,
    ai_router,
    auth,
    cart,
    catalog,
    feed,
    founding,
    groups,
    health,
    listings,
    media,
    meta,
    notifications,
    offers,
    orders,
    payments,
    pricing,
    ride_social,
    rides,
    sales,
    scan,
    sellers,
    seo,
    social,
    stores,
    streams,
    support,
    watch,
)
from .seed import seed_if_empty

logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ragnar")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
STATIC_DIR = PROJECT_ROOT / "static"
UPLOAD_DIR = PROJECT_ROOT / settings.upload_dir


@asynccontextmanager
async def lifespan(app: FastAPI):
    from .config import validate_launch_config

    report = validate_launch_config()
    for w in report["warnings"]:
        logger.warning("Config: %s", w)
    for e in report["errors"]:
        logger.error("Config: %s", e)
    if settings.is_production and not report["ok"]:
        raise RuntimeError(
            "Production config invalid — fix ENVIRONMENT variables before serving traffic: "
            + "; ".join(report["errors"])
        )

    init_db()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    seed_if_empty()
    # Retire stored theme rows from earlier brand eras so the glacial palette
    # defaults apply (custom colors staff picked deliberately are preserved).
    try:
        from sqlmodel import Session
        from .database import engine
        from .site_config import retire_legacy_theme_values

        with Session(engine) as session:
            cleared = retire_legacy_theme_values(session)
        if cleared:
            logger.info("Retired %d legacy theme setting(s).", cleared)
    except Exception:  # noqa: BLE001
        logger.exception("Legacy theme cleanup skipped")
    # Seed Counsel knowledge base so support chat works on first request.
    try:
        from sqlmodel import Session
        from .database import engine
        from .support import knowledge as support_knowledge

        with Session(engine) as session:
            support_knowledge.ensure_knowledge(session)
    except Exception:  # noqa: BLE001
        logger.exception("Support knowledge seed skipped")
    logger.info("%s v%s ready (%s).", settings.app_name, settings.version, settings.environment)
    yield


app = FastAPI(
    title="RAGNAR API",
    version=settings.version,
    description="A trust-first trading-card marketplace. "
    "Guided by counsel, driven by conquest.",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(meta.router)
app.include_router(sellers.router)
app.include_router(listings.router)
app.include_router(sales.router)
app.include_router(scan.router)
app.include_router(pricing.router)
app.include_router(payments.router)
app.include_router(catalog.router)
app.include_router(ai_router.router)
app.include_router(stores.router)
app.include_router(streams.router)
app.include_router(founding.router)
app.include_router(seo.router)
app.include_router(rides.router)
app.include_router(rides.hub)
app.include_router(ride_social.router)
app.include_router(notifications.router)
app.include_router(offers.router)
app.include_router(orders.router)
app.include_router(orders.admin_router)
app.include_router(support.router)
app.include_router(support.admin_router)
app.include_router(watch.router)
app.include_router(social.router)
app.include_router(feed.router)
app.include_router(groups.router)
app.include_router(cart.router)
app.include_router(cart.collection_router)
app.include_router(media.router)
app.include_router(admin.router)

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def home():
    # Front door = vault homepage (live breaks, vault key, founders apply).
    page = STATIC_DIR / "home.html"
    if page.exists():
        return FileResponse(str(page))
    page = STATIC_DIR / "founding.html"
    if page.exists():
        return FileResponse(str(page))
    return {"name": settings.app_name, "tagline": settings.tagline}


@app.get("/ai-tools", include_in_schema=False)
def ai_tools_page():
    page = STATIC_DIR / "ai-tools.html"
    if page.exists():
        return FileResponse(str(page))
    return {"error": "AI tools UI not found"}


@app.get("/marketplace", include_in_schema=False)
def marketplace():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"name": settings.app_name}


@app.get("/admin", include_in_schema=False)
def admin_hub():
    page = STATIC_DIR / "admin.html"
    if page.exists():
        return FileResponse(str(page))
    return {"error": "admin UI not found"}


@app.get("/stores", include_in_schema=False)
def stores_page():
    page = STATIC_DIR / "stores.html"
    if page.exists():
        return FileResponse(str(page))
    return {"error": "stores UI not found"}


@app.get("/store/{handle}", include_in_schema=False)
def store_page(handle: str):
    page = STATIC_DIR / "store.html"
    if page.exists():
        return FileResponse(str(page))
    return {"error": "store UI not found"}


@app.get("/login", include_in_schema=False)
def login_page():
    page = STATIC_DIR / "login.html"
    if page.exists():
        return FileResponse(str(page))
    return {"error": "login UI not found"}


@app.get("/verify", include_in_schema=False)
def verify_page():
    page = STATIC_DIR / "verify.html"
    if page.exists():
        return FileResponse(str(page))
    return {"error": "verify UI not found"}


@app.get("/account", include_in_schema=False)
def account_page():
    page = STATIC_DIR / "account.html"
    if page.exists():
        return FileResponse(str(page))
    return {"error": "account UI not found"}


@app.get("/listing/{listing_id}", include_in_schema=False)
def listing_page(listing_id: int):
    page = STATIC_DIR / "listing.html"
    if page.exists():
        return FileResponse(str(page))
    return {"error": "listing UI not found"}


@app.get("/support", include_in_schema=False)
def support_page():
    page = STATIC_DIR / "support.html"
    if page.exists():
        return FileResponse(str(page))
    return {"error": "support UI not found"}


@app.get("/rides", include_in_schema=False)
def rides_page():
    page = STATIC_DIR / "rides.html"
    if page.exists():
        return FileResponse(str(page))
    return {"error": "rides UI not found"}


@app.get("/ride/{ride_id}", include_in_schema=False)
def ride_page(ride_id: int):
    page = STATIC_DIR / "ride.html"
    if page.exists():
        return FileResponse(str(page))
    return {"error": "ride UI not found"}


@app.get("/live", include_in_schema=False)
def live_hub_page():
    page = STATIC_DIR / "live.html"
    if page.exists():
        return FileResponse(str(page))
    return {"error": "live hub UI not found"}


@app.get("/feed", include_in_schema=False)
def feed_page():
    page = STATIC_DIR / "feed.html"
    if page.exists():
        return FileResponse(str(page))
    return {"error": "feed UI not found"}


@app.get("/groups", include_in_schema=False)
def groups_page():
    page = STATIC_DIR / "groups.html"
    if page.exists():
        return FileResponse(str(page))
    return {"error": "groups UI not found"}


@app.get("/groups/{slug}", include_in_schema=False)
def group_page(slug: str):
    page = STATIC_DIR / "group.html"
    if page.exists():
        return FileResponse(str(page))
    return {"error": "group UI not found"}


@app.get("/mystore", include_in_schema=False)
def mystore_page():
    page = STATIC_DIR / "mystore.html"
    if page.exists():
        return FileResponse(str(page))
    return {"error": "my store UI not found"}


@app.get("/notifications", include_in_schema=False)
def notifications_page():
    page = STATIC_DIR / "notifications.html"
    if page.exists():
        return FileResponse(str(page))
    return {"error": "notifications UI not found"}


@app.get("/cart", include_in_schema=False)
def cart_page():
    page = STATIC_DIR / "cart.html"
    if page.exists():
        return FileResponse(str(page))
    return {"error": "cart UI not found"}

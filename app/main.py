"""RAGNAR marketplace — FastAPI application entrypoint.

Run locally:  uvicorn app.main:app --reload
Then open:    http://127.0.0.1:8000
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
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


def serve_page(
    filename: str,
    *,
    fallback: str | None = None,
    missing: dict[str, Any] | None = None,
):
    """Return a FileResponse for a static HTML page (or JSON if missing)."""
    page = STATIC_DIR / filename
    if page.exists():
        return FileResponse(str(page))
    if fallback:
        alt = STATIC_DIR / fallback
        if alt.exists():
            return FileResponse(str(alt))
    payload = missing if missing is not None else {"error": f"{filename} not found"}
    return JSONResponse(payload)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from sqlmodel import Session

    from .config import validate_launch_config
    from .database import engine

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

    try:
        from .site_config import retire_legacy_theme_values
        from .support import knowledge as support_knowledge

        with Session(engine) as session:
            cleared = retire_legacy_theme_values(session)
            if cleared:
                logger.info("Retired %d legacy theme setting(s).", cleared)
            support_knowledge.ensure_knowledge(session)
    except Exception:  # noqa: BLE001
        logger.exception("Startup content seed skipped")

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

for router in (
    health.router,
    auth.router,
    meta.router,
    sellers.router,
    listings.router,
    sales.router,
    scan.router,
    pricing.router,
    payments.router,
    catalog.router,
    ai_router.router,
    stores.router,
    streams.router,
    founding.router,
    seo.router,
    rides.router,
    rides.hub,
    ride_social.router,
    notifications.router,
    offers.router,
    orders.router,
    orders.admin_router,
    support.router,
    support.admin_router,
    watch.router,
    social.router,
    feed.router,
    groups.router,
    cart.router,
    cart.collection_router,
    media.router,
    admin.router,
):
    app.include_router(router)

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---- HTML pages (path params are unused; page JS reads them from the URL) ----

@app.get("/", include_in_schema=False)
def home():
    return serve_page(
        "home.html",
        fallback="founding.html",
        missing={"name": settings.app_name, "tagline": settings.tagline},
    )


@app.get("/marketplace", include_in_schema=False)
def marketplace():
    return serve_page("index.html", missing={"name": settings.app_name})


@app.get("/admin", include_in_schema=False)
def admin_hub():
    return serve_page("admin.html", missing={"error": "admin UI not found"})


@app.get("/stores", include_in_schema=False)
def stores_page():
    return serve_page("stores.html", missing={"error": "stores UI not found"})


@app.get("/store/{handle}", include_in_schema=False)
def store_page(handle: str):
    return serve_page("store.html", missing={"error": "store UI not found"})


@app.get("/login", include_in_schema=False)
def login_page():
    return serve_page("login.html", missing={"error": "login UI not found"})


@app.get("/verify", include_in_schema=False)
def verify_page():
    return serve_page("verify.html", missing={"error": "verify UI not found"})


@app.get("/account", include_in_schema=False)
def account_page():
    return serve_page("account.html", missing={"error": "account UI not found"})


@app.get("/listing/{listing_id}", include_in_schema=False)
def listing_page(listing_id: int):
    return serve_page("listing.html", missing={"error": "listing UI not found"})


@app.get("/support", include_in_schema=False)
def support_page():
    return serve_page("support.html", missing={"error": "support UI not found"})


@app.get("/rides", include_in_schema=False)
def rides_page():
    return serve_page("rides.html", missing={"error": "rides UI not found"})


@app.get("/ride/{ride_id}", include_in_schema=False)
def ride_page(ride_id: int):
    return serve_page("ride.html", missing={"error": "ride UI not found"})


@app.get("/live", include_in_schema=False)
def live_hub_page():
    return serve_page("live.html", missing={"error": "live hub UI not found"})


@app.get("/feed", include_in_schema=False)
def feed_page():
    return serve_page("feed.html", missing={"error": "feed UI not found"})


@app.get("/groups", include_in_schema=False)
def groups_page():
    return serve_page("groups.html", missing={"error": "groups UI not found"})


@app.get("/groups/{slug}", include_in_schema=False)
def group_page(slug: str):
    return serve_page("group.html", missing={"error": "group UI not found"})


@app.get("/mystore", include_in_schema=False)
def mystore_page():
    return serve_page("mystore.html", missing={"error": "my store UI not found"})


@app.get("/notifications", include_in_schema=False)
def notifications_page():
    return serve_page("notifications.html", missing={"error": "notifications UI not found"})


@app.get("/cart", include_in_schema=False)
def cart_page():
    return serve_page("cart.html", missing={"error": "cart UI not found"})

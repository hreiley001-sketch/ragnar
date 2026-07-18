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
    catalog,
    health,
    listings,
    meta,
    payments,
    pricing,
    sales,
    scan,
    sellers,
    stores,
    streams,
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
    init_db()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    seed_if_empty()
    logger.info("%s v%s ready.", settings.app_name, settings.version)
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
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
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
app.include_router(admin.router)

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def home():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"name": settings.app_name, "tagline": settings.tagline}


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

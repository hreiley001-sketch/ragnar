"""Health and version endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from ..config import settings

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/version")
def version() -> dict:
    return {
        "name": settings.app_name,
        "version": settings.version,
        "tagline": settings.tagline,
    }

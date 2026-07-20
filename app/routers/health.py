"""Health, version, and launch-config readiness."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ..config import settings, validate_launch_config

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "environment": settings.environment}


@router.get("/health/ready")
def ready() -> dict:
    """Production readiness probe — 503 when launch config has errors."""
    report = validate_launch_config()
    body = {
        "status": "ready" if report["ok"] else "not_ready",
        "environment": report["environment"],
        "errors": report["errors"],
        "warnings": report["warnings"],
        "checks": report["checks"],
    }
    if settings.is_production and not report["ok"]:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=body)
    return body


@router.get("/version")
def version() -> dict:
    return {
        "name": settings.app_name,
        "version": settings.version,
        "tagline": settings.tagline,
        "environment": settings.environment,
    }

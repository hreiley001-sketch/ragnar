"""Health, version, and launch-config readiness."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ..config import settings, validate_launch_config

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "environment": settings.environment}


@router.get("/health/architecture")
def architecture() -> dict:
    """Public map of scale boundaries (see docs/ARCHITECTURE.md)."""
    from .. import cache, webhooks_out
    from ..auth import supabase_jwt_configured
    from ..config import is_supabase_direct_db_url, is_supabase_pooler_url

    db = settings.database_url
    return {
        "map": [
            "Client → CDN → Load Balancer → FastAPI → Supabase (pooled)",
            "FastAPI → n8n (async only)",
            "Obsidian → developer documentation only",
            "Supabase Realtime → separate websocket layer",
            "Redis → caching + queues",
        ],
        "fastapi": {
            "stateless": True,
            "supabase_jwt": supabase_jwt_configured(),
            "in_memory_sessions": False,
        },
        "supabase": {
            "pooled": is_supabase_pooler_url(db) or not db.startswith("postgresql"),
            "direct_db_host": is_supabase_direct_db_url(db),
            "read_replica": bool(settings.database_read_url),
            "pool_mode": settings.db_pool_mode,
        },
        "n8n": {
            "configured": webhooks_out.n8n_configured(),
            "hot_path": False,
            "delivery": "enqueue (redis queue or background HTTP)",
        },
        "obsidian": {
            "runtime_dependency": False,
            "local_api_configured": bool(
                settings.obsidian_api_url and settings.obsidian_api_key
            ),
        },
        "cache": {
            "backend": cache.backend(),
            "redis_configured": bool(settings.redis_url),
        },
    }


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

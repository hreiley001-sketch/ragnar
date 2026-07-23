"""Platform status + controlled enqueue (staff/debug)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status

from .. import auth
from ..config import settings
from ..platform import enqueue, queue_depth, redis_ping, supabase_status
from ..platform import n8n as n8n_mod

router = APIRouter(prefix="/api/platform", tags=["platform"])


def _require_admin(
    x_admin_token: str = Header(default=""),
    user=Depends(auth.get_current_user),
) -> None:
    if auth.is_staff(user):
        return
    if settings.admin_token and x_admin_token == settings.admin_token:
        return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Admin access required (staff sign-in or admin token).",
    )


@router.get("/status")
def platform_status() -> dict:
    """Public-ish readiness of Birdman organs powering RAGNAR (no secrets)."""
    return {
        "product": "ragnar",
        "organism": "birdman",
        "hub": "Maps/RAGNAR",
        "redis": redis_ping(),
        "queue": queue_depth(),
        "n8n": n8n_mod.status(),
        "supabase": supabase_status(),
        "cache_prefix": "birdman:cache:",
        "edge": {
            "cdn": "cloudinary" if settings.cloudinary_cloud_name else "local-static",
            "rate_limit": "redis" if settings.redis_url else "in-process",
        },
    }


@router.post("/enqueue")
def platform_enqueue(
    body: dict,
    _admin: None = Depends(_require_admin),
) -> dict:
    """Staff-only: enqueue a test/ops job (async → n8n)."""
    topic = (body.get("topic") or "").strip()
    if not topic:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="topic required")
    job = enqueue(topic, body.get("payload") or {}, workflow=body.get("workflow"))
    return {"ok": True, "job": job}

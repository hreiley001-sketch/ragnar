"""Media pipeline endpoints — optimize, background-strip, and AI-enhance card
photos via Cloudinary / Remove.bg / Replicate.

All routes degrade gracefully: with no provider keys set, ``/thumb`` and
``/ingest`` return the original image and ``/enhance`` reports that no enhancer
is configured. The slow AI step runs in a ``BackgroundTask`` so the request
returns immediately.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Query,
    status,
)
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from .. import auth, media
from ..config import settings
from ..database import engine, get_session
from ..models import Listing, Seller

logger = logging.getLogger("ragnar.media")
router = APIRouter(prefix="/api/media", tags=["media"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = PROJECT_ROOT / settings.upload_dir


# --------------------------------------------------------------------------- #
# Pydantic request models (strict inbound validation)
# --------------------------------------------------------------------------- #
class IngestRequest(BaseModel):
    image_url: str = Field(..., min_length=1, max_length=1000)
    remove_bg: bool = False
    width: Optional[int] = Field(default=None, ge=16, le=4000)
    height: Optional[int] = Field(default=None, ge=16, le=4000)


class EnhanceRequest(BaseModel):
    remove_bg: bool = False
    upscale: bool = True


# --------------------------------------------------------------------------- #
# Status
# --------------------------------------------------------------------------- #
@router.get("/status")
def media_status() -> dict:
    return {
        "cloudinary": media.cloudinary_configured(),
        "remove_bg": media.removebg_configured(),
        "replicate": media.replicate_configured(),
        "background_removal": media.background_removal_available(),
    }


# --------------------------------------------------------------------------- #
# Thumbnail / delivery redirect — <img src="/api/media/thumb?url=..&w=400">
# --------------------------------------------------------------------------- #
@router.get("/thumb")
def media_thumb(
    url: str = Query(..., min_length=1, max_length=1000),
    w: int = Query(400, ge=16, le=4000),
    h: Optional[int] = Query(None, ge=16, le=4000),
    remove_bg: bool = Query(False),
) -> RedirectResponse:
    """302 to a Cloudinary-optimized URL (or the original if unconfigured)."""
    target = media.cdn_url(url, width=w, height=h, remove_bg=remove_bg)
    return RedirectResponse(url=target, status_code=302)


# --------------------------------------------------------------------------- #
# Ingest — raw image URL -> optimized (optionally background-stripped) CDN URL
# --------------------------------------------------------------------------- #
@router.post("/ingest")
async def media_ingest(payload: IngestRequest) -> dict:
    """Return an optimized delivery URL for a raw image.

    When Cloudinary is configured the asset is uploaded (so it lives on the CDN
    and gets a stable ``public_id``); otherwise a transform/fetch URL — or the
    original — is returned. WebP/auto compression is applied via ``f_auto``.
    """
    src = payload.image_url
    if media.cloudinary_configured():
        up = await media.cloudinary_upload_url(src)
        if up and up.get("public_id"):
            return {
                "url": media.cdn_url(
                    src,
                    public_id=up["public_id"],
                    width=payload.width,
                    height=payload.height,
                    remove_bg=payload.remove_bg,
                ),
                "public_id": up["public_id"],
                "optimized": True,
                "original": src,
            }
    # Graceful fallback: fetch-transform URL, or the original untouched.
    return {
        "url": media.cdn_url(
            src, width=payload.width, height=payload.height, remove_bg=payload.remove_bg
        ),
        "public_id": None,
        "optimized": media.cloudinary_configured(),
        "original": src,
    }


# --------------------------------------------------------------------------- #
# Enhance a listing photo — AI upscale + optional background removal (async)
# --------------------------------------------------------------------------- #
def _owns_listing(session: Session, user, listing: Listing) -> bool:
    if not user or not getattr(user, "seller_handle", None) or not listing.seller_id:
        return False
    seller = session.get(Seller, listing.seller_id)
    return bool(seller and seller.handle == user.seller_handle)


async def _store_bytes(data: bytes, ext: str) -> tuple[Optional[str], Optional[str]]:
    """Persist enhanced image bytes. Prefers Cloudinary; falls back to /uploads.
    Returns (url, public_id)."""
    if media.cloudinary_configured():
        up = await media.cloudinary_upload(data, f"enhanced{ext}")
        if up and up.get("secure_url"):
            return up["secure_url"], up.get("public_id")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    name = f"enh-{uuid.uuid4().hex[:12]}{ext}"
    (UPLOAD_DIR / name).write_bytes(data)
    return f"/uploads/{name}", None


async def _enhance_job(listing_id: int, remove_bg: bool, upscale: bool) -> None:
    """Background worker: strip bg and/or upscale, then persist + update the row."""
    with Session(engine) as session:
        listing = session.get(Listing, listing_id)
        if not listing or not listing.image_url:
            return
        src = listing.image_url
        new_url: Optional[str] = None
        new_public_id: Optional[str] = None

        # 1) Background removal (Remove.bg) -> PNG bytes we persist.
        if remove_bg and media.removebg_configured():
            png = await media.remove_background(src)
            if png:
                new_url, new_public_id = await _store_bytes(png, ".png")
                src = new_url

        # 2) AI upscale/restore (Replicate) -> output URL we re-persist.
        if upscale and media.replicate_configured():
            out_url = await media.replicate_upscale(src)
            if out_url:
                data = await media.fetch_bytes(out_url)
                if data:
                    new_url, new_public_id = await _store_bytes(data, ".png")
                else:
                    new_url = out_url  # store the remote URL directly

        if new_url:
            listing.image_url = new_url
            listing.image_public_id = new_public_id
            listing.image_enhanced = True
            from ..models import utcnow
            listing.updated_at = utcnow()
            session.add(listing)
            session.commit()
            logger.info("Enhanced listing %s -> %s", listing_id, new_url)


@router.post("/enhance/{listing_id}", status_code=status.HTTP_202_ACCEPTED)
def media_enhance(
    listing_id: int,
    payload: EnhanceRequest,
    background: BackgroundTasks,
    session: Session = Depends(get_session),
    user=Depends(auth.get_current_user),
    x_admin_token: str = Header(default=""),
) -> dict:
    """Queue an AI enhancement of a listing's photo. Staff or the listing owner
    only. Returns 202 immediately; the image updates in the background."""
    listing = session.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found.")

    is_admin = auth.is_staff(user) or (
        bool(settings.admin_token) and x_admin_token == settings.admin_token
    )
    if not (is_admin or _owns_listing(session, user, listing)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Only the listing owner or staff can enhance this photo.")
    if not listing.image_url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="This listing has no photo to enhance.")
    if not (media.replicate_configured() or media.removebg_configured()):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="No image-enhancement provider configured "
                                   "(set REPLICATE_API_TOKEN and/or REMOVEBG_API_KEY).")

    background.add_task(_enhance_job, listing_id, payload.remove_bg, payload.upscale)
    return {"queued": True, "listing_id": listing_id,
            "remove_bg": payload.remove_bg and media.removebg_configured(),
            "upscale": payload.upscale and media.replicate_configured()}

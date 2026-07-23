"""Scan-to-post: upload a photo, auto-recognize the card, and pull its sold
history in one call so the seller can confirm and publish."""
from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlmodel import Session

from ..comps import build_keyword, external_sold
from ..config import settings
from ..database import get_session
from ..pricing import market_price
from ..recognition import recognize
from ..schemas import MarketPrice, ScanFields, ScanResponse, SalesHistory
from ..services import match_sales, summarize_sales

logger = logging.getLogger("ragnar.scan")
router = APIRouter(prefix="/api/scan", tags=["scan"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = PROJECT_ROOT / settings.upload_dir
_ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_EXT_BY_TYPE = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
# Below this, skip paid/external enrich — recognition didn't find a real card.
_MIN_ENRICH_CONFIDENCE = 0.35


@router.post("", response_model=ScanResponse)
async def scan(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> ScanResponse:
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload must be an image file.",
        )
    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty."
        )
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image exceeds {settings.max_upload_mb} MB limit.",
        )

    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXT:
        ext = _EXT_BY_TYPE.get(file.content_type or "", ".jpg")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    name = f"scan-{uuid.uuid4().hex[:12]}{ext}"
    (UPLOAD_DIR / name).write_bytes(data)
    image_url = f"/uploads/{name}"

    result = await asyncio.to_thread(
        recognize, data, file.filename or name, file.content_type or ""
    )
    fields = result["fields"]
    confidence = float(result.get("confidence") or 0)

    sales = match_sales(
        session,
        category=fields.get("category"),
        set_name=fields.get("set_name"),
        card_number=fields.get("card_number"),
        player_or_character=fields.get("player_or_character"),
        is_graded=fields.get("is_graded"),
        grading_company=fields.get("grading_company"),
        grade=fields.get("grade"),
    )

    keyword = build_keyword(
        player_or_character=fields.get("player_or_character"),
        title=fields.get("title"),
        set_name=fields.get("set_name"),
        card_number=fields.get("card_number"),
        grading_company=fields.get("grading_company"),
        grade=fields.get("grade"),
    )
    price_query = fields.get("player_or_character") or fields.get("title") or ""
    if fields.get("set_name"):
        price_query = f"{price_query} {fields['set_name']}".strip()

    external: list = []
    mp = None
    if confidence >= _MIN_ENRICH_CONFIDENCE and (keyword or price_query):
        # Parallelize outbound enrich after recognition (comps + TCG price).
        external, mp = await asyncio.gather(
            asyncio.to_thread(external_sold, keyword),
            asyncio.to_thread(market_price, price_query, fields.get("category")),
        )
    else:
        logger.info(
            "Skipping external enrich (confidence=%.2f keyword=%r)",
            confidence,
            keyword,
        )

    history = summarize_sales(sales, external)

    return ScanResponse(
        image_url=image_url,
        provider=result["provider"],
        confidence=result["confidence"],
        notes=result["notes"],
        fields=ScanFields(**fields),
        sales_history=SalesHistory(**history),
        market_price=MarketPrice(**mp) if mp else None,
    )

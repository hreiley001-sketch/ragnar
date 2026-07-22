"""Content fetch — cached reads only; logic in content_service."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.database import get_session
from app.models import ContentItem, ContentPage
from app.services import content_service

router = APIRouter(prefix="/content", tags=["birdman-content"])


@router.get("/site", response_model=ContentItem)
def site_content(session: Session = Depends(get_session)) -> ContentItem:
    return content_service.get_site_content(session)


@router.get("/listings", response_model=ContentPage)
def listings_content(
    session: Session = Depends(get_session),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
) -> ContentPage:
    return content_service.search_listings_content(
        session, q=q, page=page, page_size=page_size
    )

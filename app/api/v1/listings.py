"""Listings — create / search / status updates."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app import auth
from app.models.marketplace import ListingCreate, ListingPage, ListingRead
from app.services import listing_service, user_service
from app.utils.exceptions import BirdmanError, NotFoundError

router = APIRouter(prefix="/listings", tags=["birdman-listings"])


class ListingStatusBody(BaseModel):
    status: str = Field(pattern="^(active|sold|cancelled)$")


@router.get("", response_model=ListingPage)
def search_listings(limit: int = Query(48, ge=1, le=100)) -> ListingPage:
    return listing_service.search_active_listings(limit=limit)


@router.post("", response_model=ListingRead, status_code=status.HTTP_201_CREATED)
def create_listing(body: ListingCreate, user=Depends(auth.require_user)) -> ListingRead:
    try:
        return listing_service.create_listing(user_service.actor_id(user), body)
    except BirdmanError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc


@router.patch("/{listing_id}", response_model=ListingRead)
def update_listing(
    listing_id: str,
    body: ListingStatusBody,
    user=Depends(auth.require_user),
) -> ListingRead:
    try:
        return listing_service.update_listing_status(
            listing_id, user_service.actor_id(user), body.status
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except BirdmanError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc

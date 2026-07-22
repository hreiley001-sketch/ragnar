"""Cards — create / list marketplace cards."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app import auth
from app.models.marketplace import CardCreate, CardRead
from app.services import card_service, user_service
from app.utils.exceptions import BirdmanError

router = APIRouter(prefix="/cards", tags=["birdman-cards"])


@router.post("", response_model=CardRead, status_code=status.HTTP_201_CREATED)
def create_card(body: CardCreate, user=Depends(auth.require_user)) -> CardRead:
    try:
        return card_service.create_card(user_service.actor_id(user), body)
    except BirdmanError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc


@router.get("", response_model=list[CardRead])
def list_cards(
    mine: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    user=Depends(auth.get_current_user),
) -> list[CardRead]:
    owner_id = user_service.actor_id(user) if mine and user else None
    if mine and user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required")
    return card_service.list_cards(owner_id, limit=limit)

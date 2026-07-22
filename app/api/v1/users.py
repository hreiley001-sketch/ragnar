"""Auth / profiles — thin surface over user_service."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session

from app import auth
from app.database import get_session
from app.models import UserProfile
from app.models.marketplace import SellerOnboard
from app.services import user_service

router = APIRouter(prefix="/users", tags=["birdman-users"])


@router.get("/me", response_model=UserProfile)
def me(request: Request, session: Session = Depends(get_session)) -> UserProfile:
    return user_service.profile_from_request(request, session)


@router.post("/seller/onboard")
def seller_onboard(
    body: SellerOnboard,
    session: Session = Depends(get_session),
    user=Depends(auth.require_user),
) -> dict[str, Any]:
    result = user_service.onboard_seller(user, body)
    session.add(user)
    session.commit()
    return result

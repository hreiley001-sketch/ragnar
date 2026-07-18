"""Seller onboarding + the Founding 250 lifecycle."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from ..database import get_session
from ..models import Seller
from ..schemas import FoundingStatus, SellerApply, SellerApplyResult, SellerState
from ..services import (
    founding_status,
    grant_founding_if_available,
    seller_state,
)

router = APIRouter(prefix="/api/sellers", tags=["sellers"])


@router.get("/founding-status", response_model=FoundingStatus)
def get_founding_status(session: Session = Depends(get_session)) -> FoundingStatus:
    return FoundingStatus(**founding_status(session))


@router.post("/apply", response_model=SellerApplyResult, status_code=status.HTTP_201_CREATED)
def apply(payload: SellerApply, session: Session = Depends(get_session)) -> SellerApplyResult:
    handle = payload.handle.strip().lower()
    existing = session.exec(select(Seller).where(Seller.handle == handle)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Handle '{handle}' is already taken.",
        )

    seller = Seller(
        handle=handle,
        display_name=payload.display_name.strip(),
        email=(payload.email or "").strip() or None,
        store_edit_token=secrets.token_urlsafe(16),
    )
    if payload.apply_for_founding:
        grant_founding_if_available(session, seller)

    session.add(seller)
    session.commit()
    session.refresh(seller)
    # store_edit_token is returned ONCE here so the seller can customize their store.
    return SellerApplyResult(**seller_state(seller), store_edit_token=seller.store_edit_token)


@router.get("/{handle}", response_model=SellerState)
def get_seller(handle: str, session: Session = Depends(get_session)) -> SellerState:
    seller = session.exec(
        select(Seller).where(Seller.handle == handle.strip().lower())
    ).first()
    if not seller:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Seller not found"
        )
    return SellerState(**seller_state(seller))

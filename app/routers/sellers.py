"""Seller onboarding + the Founding 250 lifecycle."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlmodel import Session, select

from ..auth import get_current_user, require_user
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
def apply(payload: SellerApply, session: Session = Depends(get_session),
          user=Depends(require_user)) -> SellerApplyResult:
    from ..auth import is_staff
    from ..models import IdentityStatus

    if not is_staff(user) and user.identity_status != IdentityStatus.approved.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Complete identity verification at /identity before applying to sell.",
        )
    handle = payload.handle.strip().lower()
    existing = session.exec(select(Seller).where(Seller.handle == handle)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Handle '{handle}' is already taken.",
        )
    if user.seller_handle and user.seller_handle != handle:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Your account is already linked to store '{user.seller_handle}'.",
        )

    seller = Seller(
        handle=handle,
        display_name=payload.display_name.strip(),
        email=(payload.email or "").strip() or user.email or None,
        store_edit_token=secrets.token_urlsafe(16),
    )
    if payload.apply_for_founding:
        grant_founding_if_available(session, seller)

    session.add(seller)
    # Signed-in applicants own their store automatically (no token juggling).
    if not user.seller_handle:
        user.seller_handle = handle
        session.add(user)
    session.commit()
    session.refresh(seller)
    # store_edit_token is returned ONCE here so the seller can customize their store.
    return SellerApplyResult(**seller_state(seller), store_edit_token=seller.store_edit_token)


@router.post("/claim")
def claim_store(payload: dict, session: Session = Depends(get_session),
                user=Depends(get_current_user)) -> dict:
    """Link an existing store to the signed-in account using its store token."""
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in first.")
    handle = (payload.get("handle") or "").strip().lower()
    token = (payload.get("store_token") or "").strip()
    seller = session.exec(select(Seller).where(Seller.handle == handle)).first()
    if not seller or not seller.store_edit_token or token != seller.store_edit_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Store not found or token doesn't match.")
    user.seller_handle = handle
    session.add(user)
    session.commit()
    return {"status": "claimed", "seller_handle": handle}


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

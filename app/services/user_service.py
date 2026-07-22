"""User operations — dual auth surface for Birdman API."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import Request
from sqlmodel import Session

from app import auth
from app.core import supabase_rest
from app.core.config import settings
from app.core.jobs import enqueue_job
from app.models import PublicUser, User, UserProfile
from app.models.marketplace import SellerOnboard


def actor_id(user: User) -> str:
    """Stable UUID string for marketplace FKs (Supabase sub or local synthetic)."""
    sub = getattr(user, "supabase_sub", None)
    if sub:
        return str(sub)
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"ragnar:user:{user.id}"))


def to_public_user(user: User) -> PublicUser:
    return PublicUser(
        id=user.id or 0,
        email=user.email,
        name=user.name,
        role=user.role,
        seller_handle=user.seller_handle,
        email_verified=bool(user.email_verified),
    )


def profile_from_request(request: Request, session: Session) -> UserProfile:
    """Resolve cookie or Bearer → profile. No business branching in the route."""
    user: Optional[User] = auth.get_current_user(request, session)
    if user is None:
        return UserProfile(user=None, auth="anonymous", supabase_linked=False)

    has_bearer = (request.headers.get("authorization") or "").lower().startswith("bearer ")
    has_cookie = bool(request.cookies.get(settings.session_cookie))
    if has_cookie:
        auth_mode = "cookie"
    elif has_bearer:
        auth_mode = "bearer"
    else:
        auth_mode = "anonymous"

    return UserProfile(
        user=to_public_user(user),
        auth=auth_mode,
        supabase_linked=bool(user.supabase_sub),
    )


def onboard_seller(user: User, body: SellerOnboard) -> dict[str, Any]:
    """Promote local + Supabase profile toward seller role (async notify)."""
    uid = actor_id(user)
    patch: dict[str, Any] = {"role": "seller"}
    if body.username:
        patch["username"] = body.username
    if body.profile_data:
        patch["profile_data"] = body.profile_data

    saved = supabase_rest.patch("users", {"id": f"eq.{uid}"}, patch)
    if user.role not in {"seller", "admin", "owner"}:
        user.role = "seller"
    if body.username and not user.seller_handle:
        user.seller_handle = body.username

    enqueue_job(
        "seller_notification",
        user_id=uid,
        extra={"message": "Seller onboarding started", "username": body.username},
    )
    return {
        "user_id": uid,
        "role": "seller",
        "persisted": saved is not None,
        "username": body.username or user.seller_handle,
    }

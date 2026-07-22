"""User operations — dual auth surface for Birdman API."""
from __future__ import annotations

from typing import Optional

from fastapi import Request
from sqlmodel import Session

from app import auth
from app.core.config import settings
from app.models import PublicUser, User, UserProfile


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

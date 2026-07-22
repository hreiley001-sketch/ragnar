"""Accounts & auth: password hashing (stdlib pbkdf2), session cookies, the
current-user dependency, role logic, and Google sign-in helpers.

Security note: an @ragnarips.com address only grants staff/Command-Hub access
when it's **Google-verified**. Email+password signup never grants admin (the
address isn't proven), which prevents anyone from self-registering as staff.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
from datetime import timedelta
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session, select

from .config import settings
from .database import get_session
from .models import User, UserRole, UserSession, utcnow

logger = logging.getLogger("ragnar.auth")


# --------------------------- passwords --------------------------- #

def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000)
    return f"pbkdf2_sha256$200000${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(pw: str, stored: Optional[str]) -> bool:
    if not stored:
        return False
    try:
        _, iters, salt_b64, dk_b64 = stored.split("$")
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(dk_b64)
        test = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, int(iters))
        return hmac.compare_digest(test, expected)
    except Exception:  # noqa: BLE001
        return False


# --------------------------- sessions --------------------------- #

def create_session(session: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    session.add(UserSession(
        token=token, user_id=user.id,
        expires_at=utcnow() + timedelta(days=settings.session_ttl_days),
    ))
    session.commit()
    return token


def destroy_session(session: Session, token: str) -> None:
    us = session.exec(select(UserSession).where(UserSession.token == token)).first()
    if us:
        session.delete(us)
        session.commit()


def get_current_user(
    request: Request, session: Session = Depends(get_session)
) -> Optional[User]:
    """Resolve the caller via cookie session, then Supabase Bearer JWT.

    Cookie path stays primary for the storefront. Bearer enables stateless
    FastAPI nodes + future Supabase Auth clients without dropping sessions.
    """
    token = request.cookies.get(settings.session_cookie)
    if token:
        us = session.exec(select(UserSession).where(UserSession.token == token)).first()
        if us and us.expires_at >= utcnow():
            user = session.get(User, us.user_id)
            if user:
                return user

    auth_header = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    if auth_header.lower().startswith("bearer "):
        bearer = auth_header[7:].strip()
        if bearer:
            user = user_from_supabase_bearer(session, bearer)
            if user:
                return user
    return None


def user_from_supabase_bearer(session: Session, token: str) -> Optional[User]:
    """Map a verified Supabase JWT onto a local User row (create-on-first-seen)."""
    try:
        from .platform.supabase_client import verify_jwt
    except Exception:  # noqa: BLE001
        return None

    claims = verify_jwt(token)
    if not claims:
        return None

    sub = str(claims.get("sub") or "").strip()
    email = (claims.get("email") or "").strip().lower()
    if not email and not sub:
        return None

    user: Optional[User] = None
    if sub:
        user = session.exec(select(User).where(User.supabase_sub == sub)).first()
    if user is None and email:
        user = session.exec(select(User).where(User.email == email)).first()

    if user is None:
        if not email:
            return None
        user = User(
            email=email,
            name=(claims.get("user_metadata") or {}).get("full_name")
            if isinstance(claims.get("user_metadata"), dict)
            else None,
            supabase_sub=sub or None,
            email_verified=True,
            password_hash=None,
        )
        # Staff domain still requires Google-verified path; JWT email alone
        # never auto-promotes to admin.
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    changed = False
    if sub and not user.supabase_sub:
        user.supabase_sub = sub
        changed = True
    if email and not user.email_verified and claims.get("email_confirmed_at"):
        user.email_verified = True
        changed = True
    elif email and claims.get("email") and user.email_verified is False:
        # Supabase access tokens imply a verified session for that email.
        user.email_verified = True
        changed = True
    if changed:
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


def require_user(user: Optional[User] = Depends(get_current_user)) -> User:
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required")
    return user


def is_staff(user: Optional[User]) -> bool:
    return bool(user and user.role == UserRole.admin.value)


def can_act_for_seller(user: Optional[User], seller, x_store_token: str = "") -> bool:
    """True if this request may act as the given Seller: the store token, the
    linked owner account (user.seller_handle), or staff."""
    if seller is None:
        return False
    if is_staff(user):
        return True
    if user and user.seller_handle and user.seller_handle == seller.handle:
        return True
    return bool(seller.store_edit_token) and x_store_token == seller.store_edit_token


def require_can_act_for_seller(
    user: Optional[User],
    seller,
    x_store_token: str = "",
    *,
    detail: str = "Not authorized for this store",
) -> None:
    """Raise 401 if anonymous with no store token; 403 if authenticated but not owner."""
    if can_act_for_seller(user, seller, x_store_token):
        return
    if user is None and not x_store_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


# --------------------------- roles --------------------------- #

def role_for_verified_email(email: str) -> str:
    """Role for a VERIFIED email (Google). Domain match or allowlist → admin."""
    e = (email or "").lower()
    if e in settings.admin_emails:
        return UserRole.admin.value
    if settings.staff_email_domain and e.endswith("@" + settings.staff_email_domain):
        return UserRole.admin.value
    return UserRole.user.value


def public_user(user: User) -> dict:
    return {
        "id": user.id, "email": user.email, "name": user.name,
        "role": user.role, "is_staff": user.role == UserRole.admin.value,
        "email_verified": user.email_verified, "seller_handle": user.seller_handle,
        "marketing_opt_in": bool(user.marketing_opt_in),
        "has_password": bool(user.password_hash),
        "pending_email": user.pending_email,
    }


# --------------------------- Google OAuth --------------------------- #

def google_configured() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret)


def google_redirect_uri() -> str:
    base = (settings.site_url or settings.public_base_url).rstrip("/")
    return f"{base}/api/auth/google/callback"


def google_auth_url(state: str) -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": google_redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "prompt": "select_account",
        "state": state,
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)


def google_exchange(code: str) -> dict:
    with httpx.Client(timeout=20.0) as client:
        tok = client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": google_redirect_uri(),
            },
        )
        tok.raise_for_status()
        access_token = tok.json()["access_token"]
        info = client.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        info.raise_for_status()
    return info.json()  # {email, email_verified, name, sub, ...}

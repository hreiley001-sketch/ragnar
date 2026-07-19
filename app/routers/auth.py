"""Authentication endpoints: email/password + Google sign-in."""
from __future__ import annotations

import re
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from .. import auth
from ..config import settings
from ..database import get_session
from ..emailer import send_verification_email
from ..models import User, UserRole, utcnow

def _base_url() -> str:
    return (settings.site_url or settings.public_base_url).rstrip("/")


def _is_staff_domain(email: str) -> bool:
    e = email.lower()
    return e in settings.admin_emails or (
        bool(settings.staff_email_domain) and e.endswith("@" + settings.staff_email_domain)
    )


def _send_verify(session: Session, user: User) -> bool:
    user.verify_token = secrets.token_urlsafe(24)
    user.verify_sent_at = utcnow()
    session.add(user)
    session.commit()
    link = f"{_base_url()}/verify?token={user.verify_token}"
    return send_verification_email(user.email, user.name or "", link,
                                   is_staff_domain=_is_staff_domain(user.email))

router = APIRouter(prefix="/api/auth", tags=["auth"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_SECURE = (settings.site_url or settings.public_base_url).startswith("https")


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        settings.session_cookie, token,
        max_age=settings.session_ttl_days * 86400,
        httponly=True, samesite="lax", secure=_SECURE, path="/",
    )


@router.post("/signup")
def signup(payload: dict, response: Response, session: Session = Depends(get_session)) -> dict:
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    name = (payload.get("name") or "").strip() or None
    if not name or len(name) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please enter your name.")
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a valid email.")
    if len(password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters.")
    if not payload.get("accept_terms"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please accept the Terms & buyer/seller conduct.")
    if session.exec(select(User).where(User.email == email)).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with that email already exists.")
    # Password signup is always a regular user until the email is VERIFIED.
    # Verifying an @ragnarips.com address (proving inbox control) promotes to staff.
    user = User(email=email, name=name, password_hash=auth.hash_password(password),
                email_verified=False, role=UserRole.user.value,
                marketing_opt_in=bool(payload.get("marketing_opt_in")))
    session.add(user)
    session.commit()
    session.refresh(user)
    sent = _send_verify(session, user)
    session.refresh(user)
    _set_session_cookie(response, auth.create_session(session, user))
    out = auth.public_user(user)
    out["verification_required"] = True
    out["verification_email_sent"] = sent
    out["staff_domain"] = _is_staff_domain(email)
    return out


@router.post("/verify")
def verify_email(payload: dict, response: Response, session: Session = Depends(get_session)) -> dict:
    token = (payload.get("token") or "").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing verification token.")
    user = session.exec(select(User).where(User.verify_token == token)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="This verification link is invalid or already used.")
    user.email_verified = True
    user.verify_token = None
    # Proven inbox control → promote qualifying company emails to staff.
    promoted = False
    new_role = auth.role_for_verified_email(user.email)
    if new_role == UserRole.admin.value and user.role != UserRole.admin.value:
        user.role = UserRole.admin.value
        promoted = True
    session.add(user)
    session.commit()
    session.refresh(user)
    # Log them in on this device.
    _set_session_cookie(response, auth.create_session(session, user))
    out = auth.public_user(user)
    out["verified"] = True
    out["promoted_to_staff"] = promoted
    return out


@router.post("/resend-verification")
def resend_verification(session: Session = Depends(get_session), user=Depends(auth.require_user)) -> dict:
    if user.email_verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Your email is already verified.")
    sent = _send_verify(session, user)
    return {"sent": sent, "email": user.email}


@router.post("/login")
def login(payload: dict, response: Response, session: Session = Depends(get_session)) -> dict:
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    user = session.exec(select(User).where(User.email == email)).first()
    if not user or not auth.verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    _set_session_cookie(response, auth.create_session(session, user))
    return auth.public_user(user)


@router.post("/logout")
def logout(request: Request, response: Response, session: Session = Depends(get_session)) -> dict:
    token = request.cookies.get(settings.session_cookie)
    if token:
        auth.destroy_session(session, token)
    response.delete_cookie(settings.session_cookie, path="/")
    return {"status": "logged_out"}


@router.get("/me")
def me(user=Depends(auth.get_current_user)) -> dict:
    return {"user": auth.public_user(user) if user else None, "google_enabled": auth.google_configured()}


# --------------------------- Google --------------------------- #

@router.get("/google/login")
def google_login() -> Response:
    if not auth.google_configured():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Google sign-in isn't configured yet.")
    state = secrets.token_urlsafe(16)
    resp = RedirectResponse(auth.google_auth_url(state))
    resp.set_cookie("g_state", state, max_age=600, httponly=True, samesite="lax", secure=_SECURE, path="/")
    return resp


@router.get("/google/callback")
def google_callback(request: Request, code: str = "", state: str = "",
                    session: Session = Depends(get_session)) -> Response:
    if not auth.google_configured():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google sign-in isn't configured.")
    if not code or state != request.cookies.get("g_state"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Google sign-in state.")
    try:
        info = auth.google_exchange(code)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Google sign-in failed.")

    email = (info.get("email") or "").lower()
    verified = bool(info.get("email_verified"))
    if not email or not verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google account email not verified.")

    user = session.exec(select(User).where(User.email == email)).first()
    role = auth.role_for_verified_email(email)
    if not user:
        user = User(email=email, name=info.get("name"), google_sub=info.get("sub"),
                    email_verified=True, role=role)
        session.add(user)
    else:
        user.google_sub = info.get("sub") or user.google_sub
        user.email_verified = True
        user.name = user.name or info.get("name")
        # Upgrade to staff if this verified email qualifies.
        if role == UserRole.admin.value:
            user.role = UserRole.admin.value
        session.add(user)
    session.commit()
    session.refresh(user)

    token = auth.create_session(session, user)
    dest = "/admin" if user.role == UserRole.admin.value else "/account"
    resp = RedirectResponse(dest, status_code=status.HTTP_303_SEE_OTHER)
    _set_session_cookie(resp, token)
    resp.delete_cookie("g_state", path="/")
    return resp

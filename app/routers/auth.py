"""Authentication endpoints: email/password + Google sign-in."""
from __future__ import annotations

import re
import secrets
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from .. import auth
from ..config import settings
from ..database import get_session
from ..emailer import send_password_reset_email, send_verification_email
from ..models import User, UserRole, UserSession, utcnow
from .. import ratelimit
from datetime import timedelta

def _base_url() -> str:
    return (settings.site_url or settings.public_base_url).rstrip("/")


def _is_staff_domain(email: str) -> bool:
    e = email.lower()
    return e in settings.admin_emails or (
        bool(settings.staff_email_domain) and e.endswith("@" + settings.staff_email_domain)
    )


def _send_verify(session: Session, user: User, target_email: str | None = None) -> bool:
    user.verify_token = secrets.token_urlsafe(24)
    user.verify_sent_at = utcnow()
    session.add(user)
    session.commit()
    link = f"{_base_url()}/verify?token={user.verify_token}"
    email = (target_email or user.email).strip().lower()
    return send_verification_email(email, user.name or "", link,
                                   is_staff_domain=_is_staff_domain(email))

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
def signup(payload: dict, request: Request, response: Response, session: Session = Depends(get_session)) -> dict:
    ip = ratelimit.client_ip(request)
    ratelimit.limiter.hit(
        f"signup:ip:{ip}",
        limit=ratelimit.SIGNUP_IP_LIMIT,
        window_seconds=ratelimit.SIGNUP_IP_WINDOW,
    )
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    name = (payload.get("name") or "").strip() or None
    if not name or len(name) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please enter your name.")
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a valid email.")
    if len(password) < 8 or len(password) > 128:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be 8–128 characters.")
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
    if user.verify_sent_at and utcnow() - user.verify_sent_at > timedelta(hours=24):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This verification link has expired. Request a new one from your account.",
        )
    previous_role = user.role
    if user.pending_email:
        new_email = user.pending_email.strip().lower()
        existing = session.exec(select(User).where(User.email == new_email, User.id != user.id)).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="Another account is already using that email.")
        user.email = new_email
        user.pending_email = None

    user.email_verified = True
    user.verify_token = None
    user.verify_sent_at = None
    # Proven inbox control → promote qualifying company emails to staff.
    new_role = auth.role_for_verified_email(user.email)
    user.role = new_role
    promoted = new_role == UserRole.admin.value and previous_role != UserRole.admin.value
    demoted = new_role != UserRole.admin.value and previous_role == UserRole.admin.value
    session.add(user)
    session.commit()
    session.refresh(user)
    # Log them in on this device.
    _set_session_cookie(response, auth.create_session(session, user))
    out = auth.public_user(user)
    out["verified"] = True
    out["promoted_to_staff"] = promoted
    out["demoted_from_staff"] = demoted
    return out


@router.post("/resend-verification")
def resend_verification(
    request: Request,
    session: Session = Depends(get_session),
    user=Depends(auth.require_user),
) -> dict:
    ip = ratelimit.client_ip(request)
    ratelimit.limiter.hit(
        f"resend:ip:{ip}",
        limit=ratelimit.RESEND_IP_LIMIT,
        window_seconds=ratelimit.RESEND_IP_WINDOW,
    )
    ratelimit.limiter.hit(
        f"resend:user:{user.id}",
        limit=ratelimit.RESEND_IP_LIMIT,
        window_seconds=ratelimit.RESEND_IP_WINDOW,
    )
    if user.email_verified and not user.pending_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Your email is already verified.")
    target_email = user.pending_email or user.email
    sent = _send_verify(session, user, target_email=target_email)
    return {"sent": sent, "email": target_email}


@router.post("/login")
def login(payload: dict, request: Request, response: Response, session: Session = Depends(get_session)) -> dict:
    ip = ratelimit.client_ip(request)
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    ratelimit.limiter.hit(
        f"login:ip:{ip}",
        limit=ratelimit.LOGIN_IP_LIMIT,
        window_seconds=ratelimit.LOGIN_IP_WINDOW,
    )
    if email:
        ratelimit.limiter.hit(
            f"login:email:{email}",
            limit=ratelimit.LOGIN_EMAIL_LIMIT,
            window_seconds=ratelimit.LOGIN_EMAIL_WINDOW,
        )
    user = session.exec(select(User).where(User.email == email)).first()
    if not user or not auth.verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    _set_session_cookie(response, auth.create_session(session, user))
    return auth.public_user(user)


@router.post("/forgot-password")
def forgot_password(payload: dict, request: Request, session: Session = Depends(get_session)) -> dict:
    """Always returns a generic success message to avoid email enumeration."""
    ip = ratelimit.client_ip(request)
    ratelimit.limiter.hit(
        f"forgot:ip:{ip}",
        limit=ratelimit.FORGOT_IP_LIMIT,
        window_seconds=ratelimit.FORGOT_IP_WINDOW,
    )
    email = (payload.get("email") or "").strip().lower()
    generic = {
        "status": "ok",
        "message": "If an account exists for that email, a reset link has been sent.",
    }
    if not _EMAIL_RE.match(email):
        return generic
    user = session.exec(select(User).where(User.email == email)).first()
    if user and user.password_hash:
        user.reset_token = secrets.token_urlsafe(24)
        user.reset_sent_at = utcnow()
        session.add(user)
        session.commit()
        link = f"{_base_url()}/login?reset={user.reset_token}"
        send_password_reset_email(user.email, user.name or "", link)
    return generic


@router.post("/reset-password")
def reset_password(payload: dict, response: Response, session: Session = Depends(get_session)) -> dict:
    token = (payload.get("token") or "").strip()
    new_password = payload.get("password") or ""
    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing reset token.")
    if len(new_password) < 8 or len(new_password) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be 8–128 characters.",
        )
    user = session.exec(select(User).where(User.reset_token == token)).first()
    if not user or not user.reset_sent_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="This reset link is invalid or has already been used.")
    if utcnow() - user.reset_sent_at > timedelta(hours=1):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="This reset link has expired. Request a new one.")
    user.password_hash = auth.hash_password(new_password)
    user.reset_token = None
    user.reset_sent_at = None
    session.add(user)
    # Invalidate all existing sessions after a reset.
    for us in session.exec(select(UserSession).where(UserSession.user_id == user.id)).all():
        session.delete(us)
    session.commit()
    session.refresh(user)
    _set_session_cookie(response, auth.create_session(session, user))
    return {"status": "password_reset", "user": auth.public_user(user)}


@router.post("/logout")
def logout(request: Request, response: Response, session: Session = Depends(get_session)) -> dict:
    token = request.cookies.get(settings.session_cookie)
    if token:
        auth.destroy_session(session, token)
    response.delete_cookie(settings.session_cookie, path="/")
    return {"status": "logged_out"}


@router.patch("/profile")
def update_profile(payload: dict, session: Session = Depends(get_session), user=Depends(auth.require_user)) -> dict:
    name = payload.get("name")
    marketing_opt_in = payload.get("marketing_opt_in")

    if name is not None:
        n = str(name).strip()
        if len(n) < 2:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name must be at least 2 characters.")
        if len(n) > 120:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name is too long.")
        user.name = n
    if marketing_opt_in is not None:
        user.marketing_opt_in = bool(marketing_opt_in)

    session.add(user)
    session.commit()
    session.refresh(user)
    return auth.public_user(user)


@router.post("/change-password")
def change_password(
    request: Request,
    payload: dict,
    session: Session = Depends(get_session),
    user=Depends(auth.require_user),
) -> dict:
    current_password = payload.get("current_password") or ""
    new_password = payload.get("new_password") or ""
    if not user.password_hash:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="This account uses Google sign-in. Add a password later from support.")
    if not auth.verify_password(current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect.")
    if len(new_password) < 8 or len(new_password) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be 8–128 characters.",
        )
    if auth.verify_password(new_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Choose a new password that is different from your current password.")
    user.password_hash = auth.hash_password(new_password)
    session.add(user)
    # Kill other sessions; keep the current device logged in.
    current_token = request.cookies.get(settings.session_cookie)
    for s in session.exec(select(UserSession).where(UserSession.user_id == user.id)).all():
        if not current_token or s.token != current_token:
            session.delete(s)
    session.commit()
    return {"status": "password_updated"}


@router.post("/logout-all")
def logout_all_devices(request: Request, response: Response, session: Session = Depends(get_session),
                       user=Depends(auth.require_user)) -> dict:
    token = request.cookies.get(settings.session_cookie)
    sessions = session.exec(select(UserSession).where(UserSession.user_id == user.id)).all()
    for s in sessions:
        session.delete(s)
    session.commit()
    response.delete_cookie(settings.session_cookie, path="/")
    return {"status": "logged_out_all", "count": len(sessions), "current_token": bool(token)}


@router.get("/sessions")
def list_sessions(request: Request, session: Session = Depends(get_session), user=Depends(auth.require_user)) -> dict:
    current_token = request.cookies.get(settings.session_cookie)
    sessions = session.exec(
        select(UserSession).where(UserSession.user_id == user.id).order_by(UserSession.created_at.desc())
    ).all()
    return {
        "sessions": [
            {
                "id": s.id,
                "created_at": s.created_at,
                "expires_at": s.expires_at,
                "current": bool(current_token and s.token == current_token),
            }
            for s in sessions
        ]
    }


@router.delete("/sessions/{session_id}")
def revoke_session(session_id: int, request: Request, response: Response, session: Session = Depends(get_session),
                   user=Depends(auth.require_user)) -> dict:
    us = session.get(UserSession, session_id)
    if not us or us.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    current_token = request.cookies.get(settings.session_cookie)
    is_current = bool(current_token and us.token == current_token)
    session.delete(us)
    session.commit()
    if is_current:
        response.delete_cookie(settings.session_cookie, path="/")
    return {"status": "revoked", "session_id": session_id, "was_current": is_current}


@router.post("/change-email/request")
def request_email_change(payload: dict, session: Session = Depends(get_session), user=Depends(auth.require_user)) -> dict:
    new_email = (payload.get("new_email") or "").strip().lower()
    if not _EMAIL_RE.match(new_email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a valid email.")
    if new_email == user.email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That's already your current email.")
    if session.exec(select(User).where(User.email == new_email)).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with that email already exists.")

    password = payload.get("password") or ""
    if user.password_hash:
        if not auth.verify_password(password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Password is incorrect.")
    else:
        # Google-only accounts: require typing current email as step-up.
        confirm_email = (payload.get("confirm_email") or "").strip().lower()
        if confirm_email != (user.email or "").lower():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Confirm your current email to change it on a Google account.",
            )

    user.pending_email = new_email
    session.add(user)
    session.commit()
    sent = _send_verify(session, user, target_email=new_email)
    return {"status": "verification_sent", "pending_email": new_email, "sent": sent}


@router.post("/deactivate")
def deactivate_account(payload: dict, request: Request, response: Response,
                       session: Session = Depends(get_session), user=Depends(auth.require_user)) -> dict:
    from ..models import Order

    confirm_text = (payload.get("confirm_text") or "").strip().upper()
    if confirm_text != "DEACTIVATE":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail='Type "DEACTIVATE" to confirm account closure.')

    password = payload.get("password") or ""
    if user.password_hash:
        if not auth.verify_password(password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Password is incorrect.")
    else:
        confirm_email = (payload.get("confirm_email") or "").strip().lower()
        if confirm_email != (user.email or "").lower():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Confirm your current email to deactivate a Google account.",
            )

    token = request.cookies.get(settings.session_cookie)
    sessions = session.exec(select(UserSession).where(UserSession.user_id == user.id)).all()
    for s in sessions:
        session.delete(s)

    # Scrub buyer PII on historical orders owned by this user.
    for order in session.exec(select(Order).where(Order.buyer_user_id == user.id)).all():
        order.buyer_email = None
        order.buyer_name = "Deleted User"
        session.add(order)

    # Keep row for historical FK references, but remove access and personal data.
    user.email = f"deleted+{user.id}+{int(time.time())}@example.invalid"
    user.name = "Deleted User"
    user.password_hash = None
    user.google_sub = None
    user.supabase_sub = None
    user.email_verified = False
    user.verify_token = None
    user.verify_sent_at = None
    user.pending_email = None
    user.role = UserRole.user.value
    user.seller_handle = None
    user.marketing_opt_in = False
    session.add(user)
    session.commit()

    response.delete_cookie(settings.session_cookie, path="/")
    return {"status": "account_deactivated", "session_token_present": bool(token)}


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

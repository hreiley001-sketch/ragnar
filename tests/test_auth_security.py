"""Phase 4 — password reset + rate limiting."""
from __future__ import annotations

import os
import uuid
from datetime import timedelta
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///./test_auth_security.db"
os.environ.pop("OPENAI_API_KEY", None)

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

from app.auth import hash_password
from app.database import engine, init_db
from app.main import app
from app.models import User, utcnow
from app import ratelimit

client = TestClient(app)


def setup_module(_mod=None):
    SQLModel.metadata.drop_all(engine)
    init_db()
    ratelimit.limiter.reset()


def setup_function(_fn=None):
    ratelimit.limiter.reset()


def _session():
    return Session(engine)


def _uid():
    return uuid.uuid4().hex[:8]


def _user_with_password(email: str | None = None):
    tag = _uid()
    email = email or f"u-{tag}@example.com"
    with _session() as s:
        user = User(
            email=email,
            name="Reset User",
            password_hash=hash_password("oldpassword1"),
            email_verified=True,
        )
        s.add(user)
        s.commit()
        s.refresh(user)
        return user.id, email


def test_forgot_password_generic_and_sets_token():
    _, email = _user_with_password()
    with patch("app.routers.auth.send_password_reset_email", return_value=True) as send:
        r = client.post("/api/auth/forgot-password", json={"email": email})
        assert r.status_code == 200
        assert "If an account exists" in r.json()["message"]
        assert send.called
    with _session() as s:
        from sqlmodel import select
        user = s.exec(select(User).where(User.email == email)).first()
        assert user.reset_token
        assert user.reset_sent_at


def test_forgot_unknown_email_still_ok():
    r = client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
    assert r.status_code == 200
    assert "If an account exists" in r.json()["message"]


def test_reset_password_with_valid_token():
    _, email = _user_with_password()
    with _session() as s:
        from sqlmodel import select
        user = s.exec(select(User).where(User.email == email)).first()
        user.reset_token = "tok-reset-1"
        user.reset_sent_at = utcnow()
        s.add(user)
        s.commit()
    r = client.post("/api/auth/reset-password", json={"token": "tok-reset-1", "password": "newpassword9"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "password_reset"
    # Login with new password
    r2 = client.post("/api/auth/login", json={"email": email, "password": "newpassword9"})
    assert r2.status_code == 200


def test_reset_password_expired():
    _, email = _user_with_password()
    with _session() as s:
        from sqlmodel import select
        user = s.exec(select(User).where(User.email == email)).first()
        user.reset_token = "tok-expired"
        user.reset_sent_at = utcnow() - timedelta(hours=2)
        s.add(user)
        s.commit()
    r = client.post("/api/auth/reset-password", json={"token": "tok-expired", "password": "newpassword9"})
    assert r.status_code == 400


def test_login_rate_limit():
    # Exhaust email bucket (5)
    for _ in range(5):
        r = client.post("/api/auth/login", json={"email": "rate@example.com", "password": "wrong"})
        assert r.status_code in (401, 429)
    r = client.post("/api/auth/login", json={"email": "rate@example.com", "password": "wrong"})
    assert r.status_code == 429


def test_signup_rate_limit():
    old = ratelimit.SIGNUP_IP_LIMIT
    ratelimit.SIGNUP_IP_LIMIT = 2
    try:
        for _ in range(2):
            r = client.post("/api/auth/signup", json={
                "email": f"su{_uid()}@example.com",
                "password": "password12",
                "name": "Signer",
                "accept_terms": True,
                "accept_privacy": True,
                "accept_policies": True,
            })
            assert r.status_code == 200, r.text
        r = client.post("/api/auth/signup", json={
            "email": f"su{_uid()}@example.com",
            "password": "password12",
            "name": "Signer",
            "accept_terms": True,
            "accept_privacy": True,
            "accept_policies": True,
        })
        assert r.status_code == 429
    finally:
        ratelimit.SIGNUP_IP_LIMIT = old

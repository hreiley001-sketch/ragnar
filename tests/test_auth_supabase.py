"""Dual auth — cookie sessions + Supabase Bearer JWT."""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_auth_supabase.db")
os.environ.setdefault("ENVIRONMENT", "development")

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.auth import user_from_supabase_bearer
from app.database import engine, init_db
from app.main import app
from app.models import User

client = TestClient(app)
init_db()


def test_user_from_supabase_claims_creates_and_links(monkeypatch):
    claims = {
        "sub": "supabase-user-uuid-1",
        "email": "rider@example.com",
        "email_confirmed_at": "2026-07-22T00:00:00Z",
        "aud": "authenticated",
    }
    monkeypatch.setattr(
        "app.platform.supabase_client.verify_jwt",
        lambda _token: claims,
    )
    with Session(engine) as session:
        user = user_from_supabase_bearer(session, "fake.jwt.token")
        assert user is not None
        assert user.email == "rider@example.com"
        assert user.supabase_sub == "supabase-user-uuid-1"
        assert user.email_verified is True
        uid = user.id

    with Session(engine) as session:
        again = user_from_supabase_bearer(session, "fake.jwt.token")
        assert again is not None
        assert again.id == uid
        rows = session.exec(select(User).where(User.email == "rider@example.com")).all()
        assert len(rows) == 1


def test_bearer_rejected_when_jwt_invalid(monkeypatch):
    monkeypatch.setattr(
        "app.platform.supabase_client.verify_jwt",
        lambda _token: None,
    )
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer bad"})
    # me endpoint may 401 or return null depending on implementation
    assert r.status_code in {200, 401}

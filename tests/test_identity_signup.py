"""Signup legal acceptance, AI identity gate, and ban persistence."""
from __future__ import annotations

import os
import uuid
from io import BytesIO
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite:///./test_identity_signup.db"
os.environ.pop("OPENAI_API_KEY", None)

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, select

from app import ratelimit
from app.auth import hash_password
from app.database import engine, init_db
from app.identity import hash_doc_number, record_ban
from app.main import app
from app.models import BanRecord, IdentityStatus, User, UserRole

client = TestClient(app)


def setup_module(_mod=None):
    SQLModel.metadata.drop_all(engine)
    init_db()
    ratelimit.limiter.reset()


def setup_function(_fn=None):
    ratelimit.limiter.reset()


def _uid():
    return uuid.uuid4().hex[:8]


def _signup(email: str | None = None, **extra):
    tag = _uid()
    email = email or f"s-{tag}@example.com"
    body = {
        "name": "Test User",
        "email": email,
        "password": "password123",
        "accept_terms": True,
        "accept_privacy": True,
        "accept_policies": True,
        **extra,
    }
    r = client.post("/api/auth/signup", json=body)
    return r, email


def test_signup_requires_all_legal_checkboxes():
    r = client.post("/api/auth/signup", json={
        "name": "A", "email": f"x-{_uid()}@ex.com", "password": "password123",
        "accept_terms": True,
    })
    assert r.status_code == 400


def test_signup_persists_legal_and_flags_identity():
    r, email = _signup()
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["terms_accepted"] is True
    assert data["needs_identity"] is True
    assert data["next"] == "/identity"
    with Session(engine) as s:
        u = s.exec(select(User).where(User.email == email)).first()
        assert u is not None
        assert u.terms_accepted_at is not None
        assert u.privacy_accepted_at is not None
        assert u.legal_docs_version
        assert u.identity_status == IdentityStatus.none.value


def test_banned_email_cannot_signup_again():
    tag = _uid()
    email = f"ban-{tag}@example.com"
    with Session(engine) as s:
        u = User(email=email, name="Banned", password_hash=hash_password("password123"),
                 email_verified=True, role=UserRole.user.value,
                 identity_status=IdentityStatus.none.value)
        s.add(u)
        s.commit()
        s.refresh(u)
        record_ban(s, u, reason="scam", banned_by="test")

    r = client.post("/api/auth/signup", json={
        "name": "Fake", "email": email, "password": "password123",
        "accept_terms": True, "accept_privacy": True, "accept_policies": True,
    })
    assert r.status_code == 403


def test_banned_user_cannot_login():
    tag = _uid()
    email = f"loginban-{tag}@example.com"
    with Session(engine) as s:
        u = User(email=email, name="Banned", password_hash=hash_password("password123"),
                 email_verified=True, role=UserRole.user.value)
        s.add(u)
        s.commit()
        s.refresh(u)
        record_ban(s, u, reason="fraud", banned_by="test")

    r = client.post("/api/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 403


def test_seller_apply_requires_identity():
    r, email = _signup()
    assert r.status_code == 200
    apply = client.post("/api/sellers/apply", json={
        "handle": f"h{_uid()}",
        "display_name": "Shop",
        "apply_for_founding": False,
    })
    assert apply.status_code == 403


def test_identity_submit_pending_without_openai():
    r, _ = _signup()
    assert r.status_code == 200
    # Tiny PNG
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    files = {"id_front": ("id.png", BytesIO(png), "image/png")}
    with patch("app.identity._vision_extract", return_value={
        "doc_type": "drivers_license",
        "full_name": "Test User",
        "doc_number": "D1234567",
        "country": "US",
        "looks_authentic": True,
        "confidence": 0.9,
        "notes": "ok",
        "provider": "test",
    }):
        sub = client.post("/api/auth/identity/submit", files=files)
    assert sub.status_code == 200, sub.text
    body = sub.json()
    assert body["status"] == "approved"
    assert body["user"]["identity_status"] == "approved"


def test_banned_doc_hash_blocks_identity():
    tag = _uid()
    email = f"dochash-{tag}@example.com"
    doc_hash = hash_doc_number("ZZ999999", "US")
    assert doc_hash
    with Session(engine) as s:
        s.add(BanRecord(email_normalized=f"other-{tag}@x.com", id_doc_hash=doc_hash,
                        reason="prior ban", banned_by="test"))
        s.commit()

    r, _ = _signup(email=email)
    assert r.status_code == 200
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    files = {"id_front": ("id.png", BytesIO(png), "image/png")}
    with patch("app.identity._vision_extract", return_value={
        "doc_type": "passport",
        "full_name": "Test User",
        "doc_number": "ZZ999999",
        "country": "US",
        "looks_authentic": True,
        "confidence": 0.95,
        "notes": "ok",
        "provider": "test",
    }):
        sub = client.post("/api/auth/identity/submit", files=files)
    assert sub.status_code == 403

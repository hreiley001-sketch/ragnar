"""Trust & Safety spine — suspend blocks listings; public badge; admin verify."""
from __future__ import annotations

import os
import uuid

os.environ["DATABASE_URL"] = "sqlite:///./test_trust_safety.db"
os.environ["ADMIN_TOKEN"] = "test-admin-token-trust"
os.environ.pop("OPENAI_API_KEY", None)
os.environ.pop("STRIPE_SECRET_KEY", None)

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, select

from app.auth import create_session, hash_password
from app.config import settings
from app.database import engine, init_db
from app.main import app
from app.models import (
    Category,
    Condition,
    Seller,
    SellerTrustStatus,
    User,
    UserRole,
)
from app import trust as trust_svc

COOKIE = settings.session_cookie
ADMIN_TOKEN = "test-admin-token-trust"
ADMIN = {"X-Admin-Token": ADMIN_TOKEN}


def setup_module(_mod=None):
    SQLModel.metadata.drop_all(engine)
    init_db()
    settings.admin_token = ADMIN_TOKEN


def setup_function(_fn=None):
    settings.admin_token = ADMIN_TOKEN


def _session():
    return Session(engine)


def _uid():
    return uuid.uuid4().hex[:8]


def _make_user(*, seller_handle: str | None = None):
    tag = _uid()
    with _session() as s:
        user = User(
            email=f"u-{tag}@example.com",
            name="Tester",
            password_hash=hash_password("password123"),
            email_verified=True,
            seller_handle=seller_handle,
            role=UserRole.user.value,
        )
        s.add(user)
        s.commit()
        s.refresh(user)
        token = create_session(s, user)
        return user.id, token


def _make_seller(handle: str | None = None, **extra):
    tag = _uid()
    handle = handle or f"shop{tag}"
    with _session() as s:
        seller = Seller(
            handle=handle,
            display_name=f"Shop {tag}",
            email=f"{handle}@example.com",
            store_edit_token=f"tok-{tag}",
            stripe_account_id="acct_test",
            stripe_charges_enabled=True,
            **extra,
        )
        s.add(seller)
        s.commit()
        s.refresh(seller)
        return seller.id, seller.handle, seller.store_edit_token


def _listing_payload(handle: str):
    return {
        "title": "Charizard Base Set Holo",
        "category": Category.pokemon.value,
        "set_name": "Base Set",
        "card_number": "4",
        "player_or_character": "Charizard",
        "year": 1999,
        "is_graded": False,
        "condition": Condition.near_mint.value,
        "price": 120.0,
        "shipping": 5.0,
        "quantity": 1,
        "seller_handle": handle,
    }


def test_public_trust_badge_hides_fraud_score():
    _, handle, _ = _make_seller()
    client = TestClient(app)
    r = client.get(f"/api/trust/sellers/{handle}")
    assert r.status_code == 200
    body = r.json()
    assert body["handle"] == handle
    assert body["verified"] is False
    assert body["trust_status"] == "active"
    assert body["buyer_protection"] is True
    assert "fraud_score" not in body


def test_suspended_seller_cannot_create_listing():
    _, handle, token = _make_seller()
    with _session() as s:
        seller = s.exec(select(Seller).where(Seller.handle == handle)).one()
        trust_svc.set_trust_status(
            s, seller, SellerTrustStatus.suspended.value, reason="test suspend"
        )
        s.commit()

    _, session_tok = _make_user(seller_handle=handle)
    client = TestClient(app)
    r = client.post(
        "/api/listings",
        json=_listing_payload(handle),
        cookies={COOKIE: session_tok},
        headers={"X-Store-Token": token},
    )
    assert r.status_code == 403
    assert "cannot create listings" in r.json()["detail"].lower() or "suspended" in r.json()["detail"].lower()


def test_restricted_seller_cannot_list_but_badge_shows_status():
    _, handle, tok = _make_seller()
    with _session() as s:
        seller = s.exec(select(Seller).where(Seller.handle == handle)).one()
        trust_svc.set_trust_status(
            s, seller, SellerTrustStatus.restricted.value, reason="elevated risk"
        )
        s.commit()

    client = TestClient(app)
    badge = client.get(f"/api/trust/sellers/{handle}").json()
    assert badge["trust_status"] == "restricted"

    _, session_tok = _make_user(seller_handle=handle)
    r = client.post(
        "/api/listings",
        json=_listing_payload(handle),
        cookies={COOKIE: session_tok},
        headers={"X-Store-Token": tok},
    )
    assert r.status_code == 403


def test_admin_verify_and_rescore():
    _, handle, _ = _make_seller()
    client = TestClient(app)
    r = client.post(
        f"/api/admin/trust/sellers/{handle}/verify",
        json={"verification_status": "verified", "id_verification_ref": "idv_test_1"},
        headers=ADMIN,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verified"] is True
    assert body["verification_status"] == "verified"
    assert "fraud_score" in body
    assert body["risk_band"] in {"green", "watch", "high", "critical"}

    r2 = client.post(f"/api/admin/trust/sellers/{handle}/rescore", headers=ADMIN)
    assert r2.status_code == 200
    events = client.get(f"/api/admin/trust/sellers/{handle}", headers=ADMIN).json()["events"]
    assert any(e["event_type"] == "verification_updated" for e in events)
    assert any(e["event_type"] == "fraud_score_recomputed" for e in events)


def test_admin_suspend_blocks_checkout_path_guard():
    _, handle, _ = _make_seller()
    with _session() as s:
        seller = s.exec(select(Seller).where(Seller.handle == handle)).one()
        assert trust_svc.can_sell(seller) is True
        trust_svc.set_trust_status(s, seller, "banned", reason="fraud ring")
        s.commit()
        s.refresh(seller)
        assert trust_svc.can_sell(seller) is False
        assert trust_svc.can_go_live(seller) is False

"""Seller onboarding checklist — progress, verification request, completion stamp."""
from __future__ import annotations

import os
import uuid

os.environ["DATABASE_URL"] = "sqlite:///./test_seller_onboarding.db"
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
    Listing,
    ListingStatus,
    Order,
    OrderStatus,
    Seller,
    User,
    UserRole,
)
from app import onboarding as onboarding_svc

COOKIE = settings.session_cookie


def setup_module(_mod=None):
    SQLModel.metadata.drop_all(engine)
    init_db()


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


def _make_seller(**extra):
    tag = _uid()
    handle = extra.pop("handle", None) or f"shop{tag}"
    with _session() as s:
        seller = Seller(
            handle=handle,
            display_name=f"Shop {tag}",
            email=f"{handle}@example.com",
            store_edit_token=f"tok-{tag}",
            **extra,
        )
        s.add(seller)
        s.commit()
        s.refresh(seller)
        return seller.id, seller.handle


def test_onboarding_checklist_starts_incomplete():
    sid, handle = _make_seller()
    _, token = _make_user(seller_handle=handle)
    client = TestClient(app)
    r = client.get("/api/sellers/me/onboarding", cookies={COOKIE: token})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["handle"] == handle
    assert body["complete"] is False
    assert body["progress"]["done_required"] >= 1  # create_store
    by_id = {s["id"]: s for s in body["steps"]}
    assert by_id["create_store"]["status"] == "done"
    assert by_id["connect_payouts"]["status"] == "todo"
    assert by_id["first_listing"]["status"] == "todo"
    assert by_id["first_sale"]["status"] == "todo"


def test_checklist_advances_with_payouts_listing_sale():
    sid, handle = _make_seller(stripe_account_id="acct_x", stripe_charges_enabled=True)
    with _session() as s:
        listing = Listing(
            title="Test Card",
            category=list(Category)[0].value,
            is_graded=False,
            condition=list(Condition)[0].value,
            price_cents=2500,
            quantity=1,
            seller_id=sid,
            seller_name=handle,
            status=ListingStatus.active.value,
        )
        s.add(listing)
        s.commit()
        s.refresh(listing)
        order = Order(
            listing_id=listing.id,
            seller_id=sid,
            title=listing.title,
            price_cents=2500,
            status=OrderStatus.paid.value,
            source="manual",
        )
        s.add(order)
        seller = s.get(Seller, sid)
        assert onboarding_svc.maybe_mark_complete(s, seller) is True
        s.commit()

    _, token = _make_user(seller_handle=handle)
    client = TestClient(app)
    body = client.get("/api/sellers/me/onboarding", cookies={COOKIE: token}).json()
    by_id = {s["id"]: s for s in body["steps"]}
    assert by_id["connect_payouts"]["status"] == "done"
    assert by_id["first_listing"]["status"] == "done"
    assert by_id["first_sale"]["status"] == "done"
    assert body["complete"] is True
    assert body["onboarding_completed_at"] is not None


def test_request_verification_sets_pending():
    _, handle = _make_seller()
    _, token = _make_user(seller_handle=handle)
    client = TestClient(app)
    r = client.post(
        "/api/sellers/me/onboarding/request-verification",
        cookies={COOKIE: token},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verification_status"] == "pending"
    by_id = {s["id"]: s for s in body["steps"]}
    assert by_id["get_verified"]["status"] == "pending"


def test_onboarding_requires_linked_store():
    _, token = _make_user(seller_handle=None)
    client = TestClient(app)
    r = client.get("/api/sellers/me/onboarding", cookies={COOKIE: token})
    assert r.status_code == 400

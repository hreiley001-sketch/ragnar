"""Phase 1 commerce authorization — unauthenticated and cross-seller writes must fail."""
from __future__ import annotations

import os
import uuid

os.environ["DATABASE_URL"] = "sqlite:///./test_commerce_authz.db"
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
    Seller,
    User,
    UserRole,
)

COOKIE = settings.session_cookie


def setup_module(_mod=None):
    SQLModel.metadata.drop_all(engine)
    init_db()


def _session():
    return Session(engine)


def _uid():
    return uuid.uuid4().hex[:8]


def _make_user(*, email: str | None = None, seller_handle: str | None = None, role: str = UserRole.user.value):
    tag = _uid()
    with _session() as s:
        user = User(
            email=email or f"u-{tag}@example.com",
            name="Tester",
            password_hash=hash_password("password123"),
            email_verified=True,
            seller_handle=seller_handle,
            role=role,
        )
        s.add(user)
        s.commit()
        s.refresh(user)
        token = create_session(s, user)
        return user.id, user.email, token


def _make_seller(handle: str | None = None):
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
        )
        s.add(seller)
        s.commit()
        s.refresh(seller)
        return seller.id, seller.handle, seller.store_edit_token


def _listing_payload(handle: str, **extra):
    base = {
        "title": "PSA 10 Test Card",
        "category": Category.pokemon.value if hasattr(Category, "pokemon") else list(Category)[0].value,
        "is_graded": False,
        "condition": Condition.near_mint.value if hasattr(Condition, "near_mint") else list(Condition)[0].value,
        "price": 25.0,
        "quantity": 1,
        "seller_handle": handle,
        "seller_name": handle,
    }
    base.update(extra)
    return base


def _make_listing(seller_id: int, seller_name: str):
    with _session() as s:
        cat = list(Category)[0].value
        cond = list(Condition)[0].value
        listing = Listing(
            title="Owned Card",
            category=cat,
            is_graded=False,
            condition=cond,
            price_cents=2500,
            quantity=1,
            seller_id=seller_id,
            seller_name=seller_name,
            status=ListingStatus.active.value,
        )
        s.add(listing)
        s.commit()
        s.refresh(listing)
        return listing.id


client = TestClient(app)


def test_create_listing_requires_auth():
    _, handle, _ = _make_seller()
    r = client.post("/api/listings", json=_listing_payload(handle))
    assert r.status_code == 401


def test_create_listing_binds_to_own_store():
    seller_id, handle, _ = _make_seller()
    _, _, token = _make_user(seller_handle=handle)
    r = client.post(
        "/api/listings",
        json=_listing_payload(handle),
        cookies={COOKIE: token},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["seller_name"]
    with _session() as s:
        listing = s.get(Listing, body["id"])
        assert listing is not None
        assert listing.seller_id == seller_id


def test_create_listing_rejects_other_seller_handle():
    _, handle_a, _ = _make_seller()
    _, handle_b, _ = _make_seller()
    _, _, token = _make_user(seller_handle=handle_a)
    r = client.post(
        "/api/listings",
        json=_listing_payload(handle_b),
        cookies={COOKIE: token},
    )
    assert r.status_code == 403


def test_sell_listing_requires_owner():
    seller_id, handle, _ = _make_seller()
    listing_id = _make_listing(seller_id, handle)
    # Anonymous
    r = client.post(f"/api/listings/{listing_id}/sell", json={})
    assert r.status_code in (401, 403)
    # Other seller
    _, other_handle, _ = _make_seller()
    _, _, token = _make_user(seller_handle=other_handle)
    r = client.post(
        f"/api/listings/{listing_id}/sell",
        json={},
        cookies={COOKIE: token},
    )
    assert r.status_code == 403


def test_sell_listing_owner_ok():
    seller_id, handle, _ = _make_seller()
    listing_id = _make_listing(seller_id, handle)
    _, _, token = _make_user(seller_handle=handle)
    r = client.post(
        f"/api/listings/{listing_id}/sell",
        json={},
        cookies={COOKIE: token},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "sold"


def test_update_delete_listing_owner_only():
    seller_id, handle, _ = _make_seller()
    listing_id = _make_listing(seller_id, handle)
    _, _, owner_token = _make_user(seller_handle=handle)
    _, other_handle, _ = _make_seller()
    _, _, other_token = _make_user(seller_handle=other_handle)

    r = client.patch(
        f"/api/listings/{listing_id}",
        json={"price": 40},
        cookies={COOKIE: other_token},
    )
    assert r.status_code == 403

    r = client.patch(
        f"/api/listings/{listing_id}",
        json={"price": 40},
        cookies={COOKIE: owner_token},
    )
    assert r.status_code == 200, r.text
    assert r.json()["price"] == 40.0

    r = client.delete(f"/api/listings/{listing_id}", cookies={COOKIE: other_token})
    assert r.status_code == 403

    r = client.delete(f"/api/listings/{listing_id}", cookies={COOKIE: owner_token})
    assert r.status_code == 200
    assert r.json()["status"] == "deleted"


def test_connect_requires_owner():
    _, handle, _ = _make_seller()
    r = client.post(f"/api/payments/connect/{handle}")
    assert r.status_code in (401, 403)

    _, other_handle, _ = _make_seller()
    _, _, token = _make_user(seller_handle=other_handle)
    r = client.post(f"/api/payments/connect/{handle}", cookies={COOKIE: token})
    assert r.status_code == 403


def test_checkout_requires_auth():
    seller_id, handle, _ = _make_seller()
    listing_id = _make_listing(seller_id, handle)
    r = client.post(f"/api/payments/checkout/{listing_id}", json={})
    assert r.status_code == 401


def test_seller_apply_requires_auth():
    tag = _uid()
    r = client.post(
        "/api/sellers/apply",
        json={"handle": f"new{tag}", "display_name": "New Shop", "apply_for_founding": False},
    )
    assert r.status_code == 401


def test_store_update_allows_linked_owner_session():
    _, handle, token_store = _make_seller()
    _, _, session_token = _make_user(seller_handle=handle)
    r = client.patch(
        f"/api/stores/{handle}",
        json={"tagline": "Owned storefront"},
        cookies={COOKIE: session_token},
    )
    assert r.status_code == 200, r.text
    assert r.json()["tagline"] == "Owned storefront"

    # Store token still works
    r = client.patch(
        f"/api/stores/{handle}",
        json={"tagline": "Token path"},
        headers={"X-Store-Token": token_store},
    )
    assert r.status_code == 200, r.text

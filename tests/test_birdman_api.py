"""Birdman FastAPI spine — /api/v1 surface."""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_birdman_api.db")
os.environ.setdefault("ENVIRONMENT", "development")

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_v1_pulse():
    r = client.get("/api/v1/realtime/pulse")
    assert r.status_code == 200
    body = r.json()
    assert body["organism"] == "birdman"
    assert "redis" in body
    assert "supabase" in body


def test_v1_me_anonymous():
    r = client.get("/api/v1/users/me")
    assert r.status_code == 200
    body = r.json()
    assert body["auth"] == "anonymous"
    assert body["user"] is None


def test_v1_content_site():
    r = client.get("/api/v1/content/site")
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "site_config"


def test_v1_actions_requires_auth():
    r = client.post("/api/v1/actions", json={"topic": "ops.notify", "payload": {}})
    assert r.status_code == 401


def test_core_imports():
    from app.core import cached_json, enqueue, enqueue_job, settings

    assert settings.app_name
    job = enqueue("ops.notify", {"message": "spine"}, workflow="ops/notify")
    assert job["id"]
    like = enqueue_job(
        "user_action_like",
        user_id="u1",
        content_id="c1",
        action_type="like",
    )
    assert like["workflow"] == "actions/user-like"
    assert like["payload"]["type"] == "user_action_like"
    assert "timestamp" in like["payload"]

    listing = enqueue_job(
        "listing_created",
        user_id="u1",
        extra={"listing_id": "l1", "price": 9.99},
    )
    assert listing["workflow"] == "market/listing-created"
    order = enqueue_job("order_placed", user_id="u1", extra={"order_id": "o1"})
    assert order["workflow"] == "market/order-placed"


def test_v1_listings_public():
    r = client.get("/api/v1/listings")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body


def test_v1_market_events_public():
    r = client.get("/api/v1/market-events")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body


def test_v1_cards_requires_auth():
    r = client.post("/api/v1/cards", json={"name": "Test Card"})
    assert r.status_code == 401


def test_v1_orders_requires_auth():
    r = client.post(
        "/api/v1/orders",
        json={"listing_id": "00000000-0000-0000-0000-000000000001"},
    )
    assert r.status_code == 401

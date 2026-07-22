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

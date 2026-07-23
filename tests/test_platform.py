"""Birdman platform layer — cache, queue, n8n boundary."""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_platform.db")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.pop("REDIS_URL", None)
os.environ.pop("N8N_WEBHOOK_BASE", None)
os.environ.pop("SUPABASE_URL", None)

from fastapi.testclient import TestClient

from app.core.cache import cached_json, invalidate, reset_redis
from app.core.database import supabase_status
from app.core.queue import enqueue, n8n_status, queue_depth
from app.main import app

client = TestClient(app)


def test_enqueue_local_without_redis(monkeypatch):
    reset_redis()
    monkeypatch.setattr("app.core.config.settings.redis_url", "")
    monkeypatch.setattr("app.core.config.settings.n8n_webhook_base", "")
    # settings object is shared via app.config.settings too
    monkeypatch.setattr("app.config.settings.redis_url", "")
    monkeypatch.setattr("app.config.settings.n8n_webhook_base", "")
    job = enqueue("ops.notify", {"message": "ping"}, workflow="ops/notify")
    assert job["topic"] == "ops.notify"
    assert job["id"]
    depth = queue_depth()
    assert depth["backend"] == "local"
    assert depth["depth"] >= 1


def test_cached_json_loader_without_redis(monkeypatch):
    reset_redis()
    monkeypatch.setattr("app.config.settings.redis_url", "")
    calls = {"n": 0}

    def loader():
        calls["n"] += 1
        return {"ok": True}

    a = cached_json("test:key", ttl_seconds=10, loader=loader)
    b = cached_json("test:key", ttl_seconds=10, loader=loader)
    assert a == b == {"ok": True}
    assert calls["n"] == 2
    assert invalidate("test:key") == 0


def test_n8n_skipped_when_unset(monkeypatch):
    monkeypatch.setattr("app.config.settings.n8n_webhook_base", "")
    st = n8n_status()
    assert st["enabled"] is False


def test_supabase_status_shape():
    st = supabase_status()
    assert "enabled" in st
    assert "jwt_configured" in st


def test_platform_status_endpoint():
    r = client.get("/api/platform/status")
    assert r.status_code == 200
    body = r.json()
    assert body["organism"] == "birdman"
    assert body.get("product") == "ragnar"
    assert "redis" in body
    assert "n8n" in body
    assert "supabase" in body

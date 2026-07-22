"""Scalable architecture: cache, async n8n, pooler URLs, JWT helpers."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_architecture.db")
os.environ["ENVIRONMENT"] = "development"
os.environ.pop("REDIS_URL", None)
os.environ.pop("SUPABASE_JWT_SECRET", None)
os.environ.pop("N8N_WEBHOOK_URL", None)

from app.config import (
    is_supabase_direct_db_url,
    is_supabase_pooler_url,
    normalize_database_url,
    settings,
)
from app import cache, webhooks_out


def teardown_function(_fn=None):
    settings.n8n_webhook_url = ""
    settings.n8n_webhook_secret = ""
    settings.redis_url = ""
    settings.supabase_jwt_secret = ""
    cache._store = None  # noqa: SLF001 — reset singleton between tests
    cache._store_kind = "none"  # noqa: SLF001


def test_pooler_url_detected():
    url = normalize_database_url(
        "postgresql://postgres.ref:x@aws-1-us-east-1.pooler.supabase.com:5432/postgres"
    )
    assert is_supabase_pooler_url(url)
    assert not is_supabase_direct_db_url(url)


def test_direct_db_url_detected():
    url = normalize_database_url(
        "postgresql://postgres:x@db.abcdefghijklmnop.supabase.co:5432/postgres"
    )
    assert is_supabase_direct_db_url(url)
    assert not is_supabase_pooler_url(url)


def test_cache_roundtrip_and_prefix_invalidation():
    cache.set_json("listings:search:a", {"total": 1}, ttl=60)
    cache.set_json("listings:search:b", {"total": 2}, ttl=60)
    cache.set_json("meta", {"ok": True}, ttl=60)
    assert cache.get_json("listings:search:a")["total"] == 1
    assert cache.invalidate_listings() >= 2
    assert cache.get_json("listings:search:a") is None
    assert cache.get_json("meta")["ok"] is True
    cache.invalidate_meta()
    assert cache.get_json("meta") is None


def test_n8n_enqueue_does_not_await_http(monkeypatch):
    """enqueue must return without waiting on a synchronous Client.post."""
    settings.n8n_webhook_url = "https://n8n.example/webhook/ragnar"
    settings.n8n_webhook_secret = ""
    called = {"sync_client": 0}

    class BoomClient:
        def __init__(self, *a, **k):
            called["sync_client"] += 1

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, *a, **k):
            raise AssertionError("sync httpx.Client must not be used on hot path")

    monkeypatch.setattr(webhooks_out.httpx, "Client", BoomClient)

    # Schedule path uses AsyncClient / create_task — stub AsyncClient to no-op.
    class FakeAsync:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            class R:
                status_code = 200
                text = "ok"

            return R()

    monkeypatch.setattr(webhooks_out.httpx, "AsyncClient", FakeAsync)
    assert webhooks_out.enqueue("order.paid", {"order_id": 1}) is True
    assert called["sync_client"] == 0


def test_supabase_jwt_roundtrip(monkeypatch):
    import jwt
    from app import auth

    secret = "test-jwt-secret-for-ragnar"
    settings.supabase_jwt_secret = secret
    settings.supabase_jwt_audience = "authenticated"
    token = jwt.encode(
        {
            "sub": "user-uuid-1",
            "email": "viewer@example.com",
            "aud": "authenticated",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "user_metadata": {"full_name": "Viewer One"},
        },
        secret,
        algorithm="HS256",
    )
    claims = auth.decode_supabase_jwt(token)
    assert claims is not None
    assert claims["email"] == "viewer@example.com"
    assert auth.decode_supabase_jwt("not-a-token") is None


def test_architecture_health_endpoint():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    r = client.get("/health/architecture")
    assert r.status_code == 200
    body = r.json()
    assert body["fastapi"]["stateless"] is True
    assert body["n8n"]["hot_path"] is False
    assert body["obsidian"]["runtime_dependency"] is False
    assert "Client → CDN" in body["map"][0]

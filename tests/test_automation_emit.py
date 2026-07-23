"""n8n automation emit — no-op when unset; posts when configured."""
from __future__ import annotations

import asyncio

from app import automation
from app.config import settings


def test_emit_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "automation_enabled", False)
    assert asyncio.run(automation.emit("seller.applied", {"ok": True})) is False


def test_emit_posts_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "automation_enabled", True)
    monkeypatch.setattr(settings, "n8n_webhook_base", "https://n8n.example/webhook")
    monkeypatch.setattr(settings, "n8n_webhook_secret", "sekrit")

    class _Resp:
        def raise_for_status(self):
            return None

    calls = {}

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, content=None, headers=None):
            calls["url"] = url
            calls["headers"] = headers
            calls["body"] = content
            return _Resp()

    monkeypatch.setattr(automation.httpx, "AsyncClient", _Client)
    ok = asyncio.run(automation.emit("order.paid", {"order_id": 1}))
    assert ok is True
    assert calls["url"] == "https://n8n.example/webhook/order.paid"
    assert calls["headers"]["X-Ragnar-Event"] == "order.paid"
    assert "X-Ragnar-Signature" in calls["headers"]


def test_emit_bg_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "automation_enabled", False)
    automation.emit_bg("seller.applied", {"ok": True})

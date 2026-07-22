"""n8n outbound webhooks + Obsidian markdown export."""
from __future__ import annotations

import hashlib
import hmac
import json
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_integrations.db")
os.environ["ENVIRONMENT"] = "development"
os.environ.pop("N8N_WEBHOOK_URL", None)
os.environ.pop("N8N_WEBHOOK_SECRET", None)
os.environ.pop("OBSIDIAN_API_URL", None)
os.environ.pop("OBSIDIAN_API_KEY", None)

from app.config import settings
from app.support import obsidian
from app import webhooks_out


def teardown_function(_fn=None):
    settings.n8n_webhook_url = ""
    settings.n8n_webhook_secret = ""
    settings.obsidian_api_url = ""
    settings.obsidian_api_key = ""
    settings.obsidian_vault_prefix = "RAGNAR"


def test_n8n_disabled_is_noop():
    settings.n8n_webhook_url = ""
    assert webhooks_out.n8n_configured() is False
    assert webhooks_out.dispatch("integrations.test", {"a": 1}) is False


def test_n8n_dispatch_posts_signed_payload(monkeypatch):
    settings.n8n_webhook_url = "https://n8n.example/webhook/ragnar"
    settings.n8n_webhook_secret = "sekret"
    captured: dict = {}

    class FakeResp:
        status_code = 200
        text = "ok"

    class FakeAsync:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, content=None, headers=None):
            captured["url"] = url
            captured["content"] = content
            captured["headers"] = headers
            return FakeResp()

    monkeypatch.setattr(webhooks_out.httpx, "AsyncClient", FakeAsync)
    # enqueue schedules a task; with no running loop it uses asyncio.run(_post_webhook).
    assert webhooks_out.dispatch("order.paid", {"order_id": 7}) is True
    assert captured["url"].endswith("/webhook/ragnar")
    body = json.loads(captured["content"].decode())
    assert body["event"] == "order.paid"
    assert body["source"] == "ragnar"
    assert body["data"]["order_id"] == 7
    expected = "sha256=" + hmac.new(
        b"sekret", captured["content"], hashlib.sha256
    ).hexdigest()
    assert captured["headers"]["X-Ragnar-Signature"] == expected
    assert captured["headers"]["X-Ragnar-Event"] == "order.paid"


def test_article_to_markdown_frontmatter():
    md = obsidian.article_to_markdown(
        {
            "slug": "refund-policy",
            "title": "Refund policy",
            "category": "policy",
            "tags": ["refund", "money"],
            "body": "Refunds within 30 days.",
            "rules": {"window_days_delivered": 30},
            "updated_at": "2026-07-22T00:00:00",
            "active": True,
        }
    )
    assert md.startswith("---\n")
    assert 'slug: "refund-policy"' in md
    assert "source: ragnar" in md
    assert "# Refund policy" in md
    assert "Refunds within 30 days." in md
    assert obsidian.article_path(
        {"slug": "refund-policy", "category": "policy"}
    ) == "RAGNAR/policy/refund-policy.md"


def test_obsidian_export_includes_seed_articles():
    from sqlmodel import Session, SQLModel, create_engine
    from app.support import knowledge
    from app import models  # noqa: F401

    engine = create_engine(
        "sqlite:///./test_obsidian_export.db",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        knowledge.ensure_knowledge(session)
        files = obsidian.export_vault(session)
    assert len(files) >= 5
    paths = {f["path"] for f in files}
    assert any(p.endswith("refund-policy.md") for p in paths)
    assert all(f["content"].startswith("---") for f in files)

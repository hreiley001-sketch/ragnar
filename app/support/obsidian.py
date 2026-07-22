"""Obsidian vault sync for Counsel knowledge articles.

Produces Obsidian-friendly markdown (YAML frontmatter + body). Optionally
pushes notes via the Obsidian Local REST API plugin when configured.
"""
from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import quote

import httpx
from sqlmodel import Session

from ..config import settings
from . import knowledge

logger = logging.getLogger("ragnar.obsidian")


def obsidian_configured() -> bool:
    return bool(settings.obsidian_api_url and settings.obsidian_api_key)


def article_path(article: dict[str, Any] | Any) -> str:
    """Vault-relative path, e.g. ``RAGNAR/policy/refund-policy.md``."""
    if hasattr(article, "category"):
        category = article.category or "misc"
        slug = article.slug
    else:
        category = (article.get("category") or "misc").strip() or "misc"
        slug = article.get("slug") or "untitled"
    prefix = (settings.obsidian_vault_prefix or "RAGNAR").strip().strip("/")
    return f"{prefix}/{category}/{slug}.md"


def article_to_markdown(article: dict[str, Any] | Any) -> str:
    """Render a knowledge article as Obsidian markdown with YAML frontmatter."""
    if hasattr(article, "slug"):
        slug = article.slug
        title = article.title
        category = article.category
        tags = list(article.tags or [])
        body = article.body or ""
        rules = article.rules or {}
        updated = article.updated_at.isoformat() if getattr(article, "updated_at", None) else None
        active = bool(getattr(article, "active", True))
    else:
        slug = article.get("slug") or ""
        title = article.get("title") or slug
        category = article.get("category") or "faq"
        tags = list(article.get("tags") or [])
        body = article.get("body") or ""
        rules = article.get("rules") or {}
        updated = article.get("updated_at")
        active = bool(article.get("active", True))

    # Obsidian tags: category + article tags
    tag_list = [category] + [t for t in tags if t and t != category]
    tags_yaml = ", ".join(json.dumps(t) for t in tag_list)
    rules_yaml = json.dumps(rules, ensure_ascii=False) if rules else "{}"
    front = [
        "---",
        f'title: {json.dumps(title)}',
        f'slug: {json.dumps(slug)}',
        f'category: {json.dumps(category)}',
        f"tags: [{tags_yaml}]",
        f"active: {'true' if active else 'false'}",
        f"source: ragnar",
    ]
    if updated:
        front.append(f"updated: {json.dumps(updated)}")
    front.append(f"rules: {rules_yaml}")
    front.append("---")
    front.append("")
    front.append(f"# {title}")
    front.append("")
    front.append(body.strip())
    front.append("")
    return "\n".join(front)


def export_vault(session: Session) -> list[dict[str, str]]:
    """Return ``[{path, content, slug, category, title}, ...]`` for all active articles."""
    files: list[dict[str, str]] = []
    for art in knowledge.list_articles(session):
        path = article_path(art)
        files.append(
            {
                "path": path,
                "content": article_to_markdown(art),
                "slug": art["slug"],
                "category": art["category"],
                "title": art["title"],
            }
        )
    return files


def push_note(path: str, content: str) -> bool:
    """Create/update a single note via Obsidian Local REST API. Fail-soft."""
    if not obsidian_configured():
        return False
    # Local REST API: PUT /vault/{path} with text/markdown body
    base = settings.obsidian_api_url.rstrip("/")
    url = f"{base}/vault/{quote(path, safe='/')}"
    headers = {
        "Authorization": f"Bearer {settings.obsidian_api_key}",
        "Content-Type": "text/markdown",
    }
    try:
        with httpx.Client(timeout=15.0, verify=False) as client:  # local self-signed ok
            r = client.put(url, content=content.encode("utf-8"), headers=headers)
        if r.status_code >= 400:
            logger.warning("Obsidian push %s failed %s: %s", path, r.status_code, r.text[:200])
            return False
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Obsidian push error (%s): %s", path, exc)
        return False


def sync_article(article: dict[str, Any] | Any) -> bool:
    """Push one article to Obsidian when the Local REST API is configured."""
    path = article_path(article)
    return push_note(path, article_to_markdown(article))


def sync_vault(session: Session) -> dict[str, Any]:
    """Push the full knowledge vault. Returns counts."""
    files = export_vault(session)
    if not obsidian_configured():
        return {"configured": False, "exported": len(files), "pushed": 0, "failed": 0}
    ok = fail = 0
    for f in files:
        if push_note(f["path"], f["content"]):
            ok += 1
        else:
            fail += 1
    return {"configured": True, "exported": len(files), "pushed": ok, "failed": fail}

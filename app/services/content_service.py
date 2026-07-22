"""Content retrieval + caching — heavy reads stay here, not in routes."""
from __future__ import annotations

from typing import Any, Optional

from sqlmodel import Session

from app.core.cache import cached_json
from app.core.config import settings
from app.models import ContentItem, ContentPage
from app.schemas import SortOption
from app.site_config import get_all as get_site_config_all


def get_site_content(session: Session) -> ContentItem:
    def load() -> dict[str, Any]:
        return get_site_config_all(session)

    data = cached_json(
        "site-config:public",
        ttl_seconds=settings.cache_ttl_listings_seconds,
        loader=load,
    )
    return ContentItem(id="site-config", kind="site_config", title="Site config", data=data)


def search_listings_content(
    session: Session,
    *,
    q: Optional[str] = None,
    page: int = 1,
    page_size: int = 24,
) -> ContentPage:
    """Thin wrap over marketplace listing search with Redis TTL."""
    from app.routers.listings import _search_listings_page

    cache_key = f"listings:search:v1:q={q or ''}|page={page}|ps={page_size}"

    def load() -> dict[str, Any]:
        page_obj = _search_listings_page(
            session,
            q=q,
            category=None,
            set_name=None,
            condition=None,
            grading_company=None,
            graded=None,
            min_grade=None,
            min_price=None,
            max_price=None,
            founding_only=False,
            featured=False,
            sort=SortOption.newest,
            page=page,
            page_size=page_size,
        )
        return page_obj.model_dump(mode="json")

    data = cached_json(
        cache_key,
        ttl_seconds=settings.cache_ttl_listings_seconds,
        loader=load,
    )
    items = [
        ContentItem(
            id=str(row.get("id")),
            kind="listing",
            title=row.get("title"),
            data=row,
        )
        for row in data.get("items", [])
    ]
    return ContentPage(
        items=items,
        total=int(data.get("total") or 0),
        page=int(data.get("page") or page),
        page_size=int(data.get("page_size") or page_size),
        cached=bool(settings.redis_url),
    )

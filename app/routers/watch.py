"""Watchlist + saved searches with new-listing alert matching.

Two surfaces share this file (``/api/watch`` and ``/api/searches``), so the
router has no prefix and every route declares its full path.

``match_new_listing(session, listing)`` is the alert matcher the listings
create-path calls: it fans out "saved_search" notifications to every user whose
saved filters match the freshly created listing. It must never raise — alerts
can never be allowed to break listing creation.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlmodel import Session, select

from ..auth import get_current_user, require_user
from ..database import get_session
from ..models import Listing, SavedSearch, User, WatchItem
from ..notify import notify
from ..schemas import ListingRead

logger = logging.getLogger("ragnar.watch")

router = APIRouter(tags=["watch"])


# --------------------------------------------------------------------------- #
# Watchlist
# --------------------------------------------------------------------------- #


class WatchToggle(BaseModel):
    listing_id: int


def _watcher_count(session: Session, listing_id: int) -> int:
    return session.exec(
        select(func.count()).select_from(WatchItem).where(WatchItem.listing_id == listing_id)
    ).one()


@router.post("/api/watch")
def toggle_watch(
    payload: WatchToggle,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    """Toggle a listing on/off the current user's watchlist."""
    listing = session.get(Listing, payload.listing_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")

    existing = session.exec(
        select(WatchItem).where(
            WatchItem.user_id == user.id, WatchItem.listing_id == listing.id
        )
    ).first()

    if existing:
        session.delete(existing)
        session.commit()
        watching = False
    else:
        session.add(WatchItem(user_id=user.id, listing_id=listing.id))
        session.commit()
        watching = True

    return {"watching": watching, "count": _watcher_count(session, listing.id)}


@router.get("/api/watch/mine")
def my_watchlist(
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    """The current user's watched listings, newest watch first."""
    watches = session.exec(
        select(WatchItem)
        .where(WatchItem.user_id == user.id)
        .order_by(WatchItem.created_at.desc(), WatchItem.id.desc())
    ).all()

    items: list[dict] = []
    for w in watches:
        listing = session.get(Listing, w.listing_id)
        if not listing:  # listing was deleted — skip the orphaned watch
            continue
        data = ListingRead.from_listing(listing).model_dump(mode="json")
        data["watch_id"] = w.id
        items.append(data)
    return {"items": items}


@router.get("/api/watch/status")
def watch_status(
    ids: str = Query(default="", description="Comma-separated listing ids, e.g. 1,2,3"),
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
) -> dict:
    """Which of the given listing ids the current user watches. Anonymous → {}."""
    if not user:
        return {}

    listing_ids: list[int] = []
    for part in (ids or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            listing_ids.append(int(part))
        except ValueError:
            continue
    if not listing_ids:
        return {}

    watched = session.exec(
        select(WatchItem.listing_id).where(
            WatchItem.user_id == user.id,
            WatchItem.listing_id.in_(listing_ids),  # type: ignore[attr-defined]
        )
    ).all()
    return {str(lid): True for lid in watched}


# --------------------------------------------------------------------------- #
# Saved searches
# --------------------------------------------------------------------------- #

class SavedSearchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    filters: dict = Field(default_factory=dict)


def _clean_filters(raw: dict) -> dict:
    """Whitelist + coerce the filter keys we understand; drop everything else."""
    clean: dict = {}
    if not isinstance(raw, dict):
        return clean
    for key in ("q", "category", "grading_company"):
        v = raw.get(key)
        if isinstance(v, str) and v.strip():
            clean[key] = v.strip()
    v = raw.get("graded")
    if isinstance(v, bool):
        clean["graded"] = v
    for key in ("min_grade", "min_price", "max_price"):
        v = raw.get(key)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            clean[key] = float(v)
    return clean


@router.post("/api/searches")
def create_search(
    payload: SavedSearchCreate,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name is required")
    s = SavedSearch(user_id=user.id, name=name[:80], filters=_clean_filters(payload.filters))
    session.add(s)
    session.commit()
    session.refresh(s)
    return {"id": s.id, "name": s.name, "filters": s.filters}


@router.get("/api/searches/mine")
def my_searches(
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    searches = session.exec(
        select(SavedSearch)
        .where(SavedSearch.user_id == user.id)
        .order_by(SavedSearch.created_at.desc(), SavedSearch.id.desc())
    ).all()
    return {
        "items": [
            {
                "id": s.id,
                "name": s.name,
                "filters": s.filters or {},
                "created_at": s.created_at.isoformat(),
            }
            for s in searches
        ]
    }


@router.delete("/api/searches/{search_id}")
def delete_search(
    search_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    s = session.get(SavedSearch, search_id)
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved search not found")
    if s.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your saved search")
    session.delete(s)
    session.commit()
    return {"status": "deleted"}


# --------------------------------------------------------------------------- #
# Alert matcher — called by the listings create-path
# --------------------------------------------------------------------------- #

def _search_matches(filters: dict, listing: Listing, haystack: str) -> bool:
    """True when EVERY provided filter passes for this listing."""
    q = filters.get("q")
    if q is not None and str(q).lower() not in haystack:
        return False

    category = filters.get("category")
    if category is not None and category != listing.category:
        return False

    graded = filters.get("graded")
    if graded is not None and bool(graded) != listing.is_graded:
        return False

    grading_company = filters.get("grading_company")
    if grading_company is not None and grading_company != listing.grading_company:
        return False

    min_grade = filters.get("min_grade")
    if min_grade is not None and (listing.grade is None or listing.grade < float(min_grade)):
        return False

    price = listing.price_cents / 100
    min_price = filters.get("min_price")
    if min_price is not None and price < float(min_price):
        return False

    max_price = filters.get("max_price")
    if max_price is not None and price > float(max_price):
        return False

    return True


def match_new_listing(session: Session, listing: Listing) -> int:
    """Notify every user whose saved search matches a newly created listing.

    Returns the number of matched searches. Never raises — a broken alert must
    never break listing creation.
    """
    try:
        haystack = (
            f"{listing.title} {listing.player_or_character or ''} {listing.set_name or ''}"
        ).lower()
        matched = 0
        for s in session.exec(select(SavedSearch)).all():
            filters = s.filters or {}
            if not isinstance(filters, dict) or not _search_matches(filters, listing, haystack):
                continue
            notify(
                session,
                s.user_id,
                "saved_search",
                f"New match: {listing.title}",
                body=f"Matches your saved search '{s.name}'",
                link=f"/listing/{listing.id}",
                commit=False,
            )
            matched += 1
        if matched:
            session.commit()
        return matched
    except Exception as exc:  # noqa: BLE001
        logger.warning("saved-search matching failed for listing %s: %s", listing.id, exc)
        return 0

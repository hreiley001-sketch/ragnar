"""Listing query service — storefront search lives here (not in routers).

Used by legacy `/api/listings` and Birdman `/api/v1/content|marketplace`.
"""
from __future__ import annotations

import math
from typing import Optional

from sqlalchemy import func
from sqlmodel import Session, or_, select

from app.models import (
    Category,
    Condition,
    GradingCompany,
    Listing,
    ListingStatus,
)
from app.schemas import ListingPage, ListingRead, SortOption


def search_listings_page(
    session: Session,
    *,
    q: str | None = None,
    category: Category | None = None,
    set_name: str | None = None,
    condition: Condition | None = None,
    grading_company: GradingCompany | None = None,
    graded: bool | None = None,
    min_grade: float | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    founding_only: bool = False,
    featured: bool = False,
    sort: SortOption = SortOption.newest,
    page: int = 1,
    page_size: int = 24,
) -> ListingPage:
    filters = [Listing.status == ListingStatus.active.value]

    if q:
        like = f"%{q.strip()}%"
        filters.append(
            or_(
                Listing.title.ilike(like),
                Listing.player_or_character.ilike(like),
                Listing.set_name.ilike(like),
            )
        )
    if category:
        filters.append(Listing.category == category.value)
    if set_name:
        filters.append(Listing.set_name.ilike(f"%{set_name.strip()}%"))
    if condition:
        filters.append(Listing.condition == condition.value)
    if grading_company:
        filters.append(Listing.grading_company == grading_company.value)
    if graded is not None:
        filters.append(Listing.is_graded == graded)
    if min_grade is not None:
        filters.append(Listing.grade >= min_grade)
    if min_price is not None:
        filters.append(Listing.price_cents >= round(min_price * 100))
    if max_price is not None:
        filters.append(Listing.price_cents <= round(max_price * 100))
    if founding_only:
        filters.append(Listing.is_founding_seller == True)  # noqa: E712
    if featured:
        filters.append(Listing.is_featured == True)  # noqa: E712

    total = session.exec(
        select(func.count()).select_from(Listing).where(*filters)
    ).one()

    statement = select(Listing).where(*filters)
    if sort == SortOption.price_asc:
        statement = statement.order_by(Listing.price_cents.asc())
    elif sort == SortOption.price_desc:
        statement = statement.order_by(Listing.price_cents.desc())
    elif sort == SortOption.grade_desc:
        statement = statement.order_by(Listing.grade.desc(), Listing.created_at.desc())
    else:
        statement = statement.order_by(Listing.created_at.desc())

    statement = statement.offset((page - 1) * page_size).limit(page_size)
    rows = session.exec(statement).all()

    return ListingPage(
        items=[ListingRead.from_listing(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)) if total else 0,
    )

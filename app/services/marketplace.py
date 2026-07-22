"""Business logic shared across routers: Founding-250 seller state, effective
fee rates, and sold-comp matching/aggregation for sales history.

Founders program: the first 250 sellers to sign up get a 4% platform fee,
flat, forever. Every seller after that pays the 5% standard rate. There is
no dollar cap, no sales threshold, and no time window — just a permanent
rate for being one of the first 250.
"""
from __future__ import annotations

import statistics
from datetime import timedelta
from typing import Optional

from sqlmodel import Session, func, select

from app.config import settings
from app.models import Listing, ListingStatus, Sale, Seller, utcnow

# --------------------------------------------------------------------------- #
# Founding 250 / fee state
# --------------------------------------------------------------------------- #


def founding_intro_active(seller: Optional[Seller]) -> bool:
    """Back-compat alias — Founding status itself is the whole benefit now
    (flat 4% forever), so this is just ``is_founding``."""
    return bool(seller and seller.is_founding)


def effective_platform_rate(seller: Optional[Seller]) -> float:
    """The platform take rate for this seller: 4% flat forever if they're one
    of the Founding 250, else the 5% standard rate."""
    if seller and seller.is_founding:
        return settings.founding_rate
    return settings.standard_rate


def seller_state(seller: Seller) -> dict:
    """Serializable snapshot of a seller's Founding status for the API/UI."""
    return {
        "handle": seller.handle,
        "display_name": seller.display_name,
        "is_founding": seller.is_founding,
        "founding_number": seller.founding_number,
        "intro_active": seller.is_founding,
        "intro_ends_at": None,
        "intro_days_left": None,
        "intro_sales_remaining": None,
        "effective_rate": effective_platform_rate(seller),
    }


def founding_status(session: Session) -> dict:
    claimed = session.exec(
        select(func.count()).select_from(Seller).where(Seller.is_founding == True)  # noqa: E712
    ).one()
    return {
        "claimed": claimed,
        "cap": settings.founding_cap,
        "remaining": max(0, settings.founding_cap - claimed),
        "intro_days": settings.founding_intro_days,
        "intro_sales_cap": settings.founding_intro_sales_cap,
    }


def grant_founding_if_available(session: Session, seller: Seller) -> None:
    """Give the seller permanent Founding status (flat 4% forever) if one of
    the first 250 slots remain. Caller commits."""
    status = founding_status(session)
    if status["remaining"] <= 0:
        return
    seller.is_founding = True
    seller.founding_number = status["claimed"] + 1
    seller.founding_activated_at = utcnow()


# --------------------------------------------------------------------------- #
# Sold comps / sales history
# --------------------------------------------------------------------------- #


def match_sales(
    session: Session,
    *,
    category: Optional[str] = None,
    set_name: Optional[str] = None,
    card_number: Optional[str] = None,
    player_or_character: Optional[str] = None,
    is_graded: Optional[bool] = None,
    grading_company: Optional[str] = None,
    grade: Optional[float] = None,
    lookback_days: Optional[int] = None,
    limit: int = 50,
) -> list[Sale]:
    """Find comparable completed sales for a card identity.

    Deliberately lenient on descriptive fields (so we surface *something*) but
    strict on grade when graded — a PSA 10 comp is not a PSA 8 comp.
    """
    lookback = lookback_days or settings.comps_lookback_days
    since = utcnow() - timedelta(days=lookback)
    filters = [Sale.sold_at >= since]

    if category:
        filters.append(Sale.category == category)
    if card_number:
        filters.append(Sale.card_number == card_number)
    if set_name:
        filters.append(Sale.set_name.ilike(f"%{set_name.strip()}%"))
    if player_or_character:
        filters.append(Sale.player_or_character.ilike(f"%{player_or_character.strip()}%"))
    if is_graded is not None:
        filters.append(Sale.is_graded == is_graded)
    if is_graded and grading_company:
        filters.append(Sale.grading_company == grading_company)
    if is_graded and grade is not None:
        filters.append(Sale.grade == grade)

    statement = (
        select(Sale).where(*filters).order_by(Sale.sold_at.desc()).limit(limit)
    )
    return list(session.exec(statement).all())


def sale_to_comp(s: Sale) -> dict:
    """Normalize a stored Sale into the common comp dict shape."""
    return {
        "price": round(s.sold_price_cents / 100, 2),
        "sold_at": s.sold_at,
        "grading_company": s.grading_company,
        "grade": s.grade,
        "condition": s.condition,
        "source": s.source,
    }


def _empty_history() -> dict:
    return {
        "count": 0, "average": None, "median": None, "low": None, "high": None,
        "last_price": None, "last_sold_at": None, "suggested_price": None,
        "series": [], "recent": [],
    }


def summarize_comps(comps: list[dict]) -> dict:
    """Aggregate comp dicts ({price, sold_at, ...}) from any source into headline
    stats + a time series for a sparkline. Median is the suggested price (more
    honest than a mean skewed by one hot sale)."""
    comps = [c for c in comps if c.get("price") is not None and c.get("sold_at")]
    if not comps:
        return _empty_history()

    prices = [c["price"] for c in comps]
    by_date = sorted(comps, key=lambda c: c["sold_at"])
    latest = by_date[-1]
    by_recent = sorted(comps, key=lambda c: c["sold_at"], reverse=True)
    median = round(statistics.median(prices), 2)

    return {
        "count": len(comps),
        "average": round(sum(prices) / len(prices), 2),
        "median": median,
        "low": round(min(prices), 2),
        "high": round(max(prices), 2),
        "last_price": round(latest["price"], 2),
        "last_sold_at": latest["sold_at"],
        "suggested_price": median,
        "series": [
            {"date": c["sold_at"].date().isoformat(), "price": round(c["price"], 2)}
            for c in by_date
        ],
        "recent": [
            {
                "price": round(c["price"], 2),
                "sold_at": c["sold_at"],
                "grading_company": c.get("grading_company"),
                "grade": c.get("grade"),
                "condition": c.get("condition"),
                "source": c.get("source", "ragnar"),
            }
            for c in by_recent[:12]
        ],
    }


def summarize_sales(sales: list[Sale], external: list[dict] | None = None) -> dict:
    """Backward-compatible: aggregate stored Sales plus any external comps."""
    comps = [sale_to_comp(s) for s in sales] + list(external or [])
    return summarize_comps(comps)


def record_sale(
    session: Session,
    listing: Listing,
    price_cents: int,
    *,
    source: str = "ragnar",
    units: int = 1,
) -> Sale:
    """Record a sold unit and update inventory.

    Decrements ``listing.quantity`` by ``units``. Marks the listing sold when
    remaining quantity hits zero. Shared by manual /sell and Stripe webhook.
    Caller commits.
    """
    sale = Sale(
        listing_id=listing.id,
        category=listing.category,
        set_name=listing.set_name,
        card_number=listing.card_number,
        player_or_character=listing.player_or_character,
        is_graded=listing.is_graded,
        grading_company=listing.grading_company,
        grade=listing.grade,
        condition=listing.condition,
        sold_price_cents=price_cents,
        source=source,
    )
    remaining = max(0, int(listing.quantity or 0) - max(1, units))
    listing.quantity = remaining
    if remaining <= 0:
        listing.status = ListingStatus.sold.value
    listing.updated_at = utcnow()
    session.add(sale)
    session.add(listing)
    return sale

"""RAGNAR Command Hub — admin API.

All endpoints require the header  X-Admin-Token: <ADMIN_TOKEN>.
If ADMIN_TOKEN is unset, admin is disabled (503) — secure by default.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func
from sqlmodel import Session, select

from .. import ai, catalog, comps, payments, pricing
from ..config import settings
from ..database import get_session
from ..models import Listing, ListingStatus, Sale, Seller
from ..recognition import active_provider
from ..schemas import ListingRead
from ..services import founding_status, record_sale

router = APIRouter(prefix="/api/admin", tags=["admin"])


def require_admin(x_admin_token: str = Header(default="")) -> None:
    if not settings.admin_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin is disabled. Set ADMIN_TOKEN to enable the command hub.",
        )
    if x_admin_token != settings.admin_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")


def integrations_status() -> dict:
    return {
        "recognition": active_provider(),
        "live_pricing": pricing.is_configured(),
        "external_comps": comps.is_configured(),
        "ai": ai.is_configured(),
        "catalog": True,  # Scryfall/Pokémon TCG are free/no-key
        "payments": payments.status(),
        "psa": bool(settings.psa_access_token),
    }


@router.get("/check")
def check(_: None = Depends(require_admin)) -> dict:
    return {"ok": True}


@router.get("/stats")
def stats(session: Session = Depends(get_session), _: None = Depends(require_admin)) -> dict:
    def count(*where) -> int:
        return session.exec(select(func.count()).select_from(Listing).where(*where)).one()

    active = count(Listing.status == ListingStatus.active.value)
    sold = count(Listing.status == ListingStatus.sold.value)
    total = count()

    own_sales = session.exec(
        select(Sale).where(Sale.source.in_(["ragnar", "stripe"]))
    ).all()
    gmv_cents = sum(s.sold_price_cents for s in own_sales)
    revenue_cents = round(gmv_cents * settings.standard_rate)  # estimate

    sellers_total = session.exec(select(func.count()).select_from(Seller)).one()
    active_value_cents = session.exec(
        select(func.coalesce(func.sum(Listing.price_cents), 0)).where(
            Listing.status == ListingStatus.active.value
        )
    ).one()

    return {
        "listings": {"total": total, "active": active, "sold": sold},
        "active_inventory_value": round(active_value_cents / 100, 2),
        "gmv": round(gmv_cents / 100, 2),
        "estimated_platform_revenue": round(revenue_cents / 100, 2),
        "orders": len(own_sales),
        "sellers": {"total": sellers_total},
        "founding": founding_status(session),
        "integrations": integrations_status(),
    }


@router.get("/listings")
def admin_listings(
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
    q: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    filters = []
    if q:
        filters.append(Listing.title.ilike(f"%{q.strip()}%"))
    if status_filter:
        filters.append(Listing.status == status_filter)
    rows = session.exec(
        select(Listing).where(*filters).order_by(Listing.created_at.desc()).limit(limit)
    ).all()
    return {"items": [ListingRead.from_listing(r).model_dump() for r in rows], "count": len(rows)}


@router.patch("/listings/{listing_id}")
def admin_update_listing(
    listing_id: int,
    payload: dict,
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
) -> dict:
    listing = session.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    if "price" in payload and payload["price"] is not None:
        listing.price_cents = round(float(payload["price"]) * 100)
    if payload.get("status") in {s.value for s in ListingStatus}:
        listing.status = payload["status"]
    session.add(listing)
    session.commit()
    session.refresh(listing)
    return ListingRead.from_listing(listing).model_dump()


@router.post("/listings/{listing_id}/mark-sold")
def admin_mark_sold(
    listing_id: int,
    payload: dict | None = None,
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
) -> dict:
    listing = session.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    if listing.status == ListingStatus.sold.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already sold")
    price = (payload or {}).get("price")
    price_cents = round(float(price) * 100) if price else listing.price_cents
    sale = record_sale(session, listing, price_cents, source="ragnar")
    session.commit()
    session.refresh(sale)
    return {"status": "sold", "sale_id": sale.id, "sold_price": round(price_cents / 100, 2)}


@router.delete("/listings/{listing_id}")
def admin_delete_listing(
    listing_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
) -> dict:
    listing = session.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    session.delete(listing)
    session.commit()
    return {"status": "deleted", "id": listing_id}


@router.get("/sellers")
def admin_sellers(session: Session = Depends(get_session), _: None = Depends(require_admin)) -> dict:
    rows = session.exec(select(Seller).order_by(Seller.created_at.desc())).all()
    items = [{
        "handle": s.handle,
        "display_name": s.display_name,
        "email": s.email,
        "is_founding": s.is_founding,
        "founding_number": s.founding_number,
        "founding_intro_sales": round(s.founding_intro_sales_cents / 100, 2),
        "stripe_connected": bool(s.stripe_account_id),
        "stripe_charges_enabled": s.stripe_charges_enabled,
    } for s in rows]
    return {"items": items, "count": len(items)}


@router.get("/sales")
def admin_sales(
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    rows = session.exec(
        select(Sale).where(Sale.source.in_(["ragnar", "stripe"]))
        .order_by(Sale.sold_at.desc()).limit(limit)
    ).all()
    items = [{
        "id": s.id,
        "category": s.category,
        "player_or_character": s.player_or_character,
        "set_name": s.set_name,
        "grading_company": s.grading_company,
        "grade": s.grade,
        "price": round(s.sold_price_cents / 100, 2),
        "sold_at": s.sold_at.isoformat(),
        "source": s.source,
    } for s in rows]
    return {"items": items, "count": len(items)}

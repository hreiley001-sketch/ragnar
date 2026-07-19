"""RAGNAR Command Hub — admin API.

All endpoints require the header  X-Admin-Token: <ADMIN_TOKEN>.
If ADMIN_TOKEN is unset, admin is disabled (503) — secure by default.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func
from sqlmodel import Session, select

import secrets

from .. import ai, auth, catalog, comps, payments, pricing, seo_tools
from ..config import settings
from ..database import get_session
from ..models import (
    FoundingApplication,
    Listing,
    ListingStatus,
    LiveStream,
    Sale,
    Seller,
    User,
    UserRole,
    UserSession,
)
from ..recognition import active_provider
from ..schemas import FoundingApplicationRead, ListingRead
from ..services import founding_status, grant_founding_if_available, record_sale

router = APIRouter(prefix="/api/admin", tags=["admin"])


def require_admin(
    x_admin_token: str = Header(default=""),
    user=Depends(auth.get_current_user),
) -> None:
    # 1) Signed-in staff (verified @ragnarips.com or allow-listed) — preferred.
    if auth.is_staff(user):
        return
    # 2) Break-glass admin token.
    if settings.admin_token and x_admin_token == settings.admin_token:
        return
    if not settings.admin_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin is disabled. Sign in with a staff @ragnarips.com account "
            "(configure Google sign-in) or set ADMIN_TOKEN.",
        )
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Admin access required (staff sign-in or admin token).")


def integrations_status() -> dict:
    return {
        "recognition": active_provider(),
        "live_pricing": pricing.is_configured(),
        "external_comps": comps.is_configured(),
        "ai": ai.is_configured(),
        "catalog": True,  # Scryfall/Pokémon TCG are free/no-key
        "payments": payments.status(),
        "psa": bool(settings.psa_access_token),
        "seo": seo_tools.providers_status(),
    }


@router.get("/users")
def admin_users(
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
    q: Optional[str] = Query(None),
) -> dict:
    stmt = select(User).order_by(User.created_at.desc())
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where((User.email.ilike(like)) | (User.name.ilike(like)))
    rows = session.exec(stmt.limit(500)).all()
    return {"items": [{
        "id": u.id, "email": u.email, "name": u.name, "role": u.role,
        "is_staff": u.role == UserRole.admin.value, "email_verified": u.email_verified,
        "seller_handle": u.seller_handle, "created_at": u.created_at.isoformat(),
    } for u in rows], "count": len(rows)}


@router.post("/staff")
def admin_set_staff(
    payload: dict,
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
) -> dict:
    """Grant or revoke Command Hub (staff) access for a user by email."""
    email = (payload.get("email") or "").strip().lower()
    make_staff = bool(payload.get("make_staff", True))
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="No account with that email (they must sign up first).")
    user.role = UserRole.admin.value if make_staff else UserRole.user.value
    session.add(user)
    session.commit()
    if make_staff:
        from ..notify import notify
        notify(session, user.id, "staff_granted", "You now have Command Hub access",
               body="An admin granted your account staff access.", link="/admin")
    return {"email": user.email, "role": user.role, "is_staff": user.role == UserRole.admin.value}


@router.delete("/users/{user_id}")
def admin_delete_user(
    user_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
    force: bool = Query(False, description="Delete even if the user operates a store."),
) -> dict:
    """Remove a user account (offboarding, spam/test cleanup). Invalidates their
    sessions. Refuses to delete a user linked to a seller store unless force=true,
    so sale history and an active shop are never orphaned by accident."""
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such user.")
    if user.seller_handle and not force:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This user operates store '{user.seller_handle}'. Pass force=true to delete anyway.",
        )
    email = user.email
    for s in session.exec(select(UserSession).where(UserSession.user_id == user_id)).all():
        session.delete(s)
    session.delete(user)
    session.commit()
    return {"deleted": True, "email": email, "id": user_id}


@router.get("/site-config")
def admin_site_config(
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
) -> dict:
    """The site-content registry + current values, for the hub's Site editor."""
    from .. import site_config
    return {"fields": site_config.field_specs(session)}


@router.put("/site-config")
def admin_update_site_config(
    payload: dict,
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
    user=Depends(auth.get_current_user),
    x_admin_token: str = Header(default=""),
) -> dict:
    """Save staff edits to whitelisted site content. Records who made the change."""
    from .. import site_config
    by = (getattr(user, "email", None) or ("admin-token" if x_admin_token else "staff"))
    updates = payload.get("updates") if isinstance(payload.get("updates"), dict) else payload
    config = site_config.set_many(session, updates or {}, by)
    return {"saved": True, "by": by, "config": config}


@router.post("/scrape-price")
async def admin_scrape_price(payload: dict, _: None = Depends(require_admin)) -> dict:
    """Scrape a card page (any marketplace/price-guide URL) via Firecrawl and
    return high/low/avg prices found on it — pricing-intelligence research."""
    from ..enrich import scrape_price
    url = (payload.get("url") or "").strip()
    if not url.startswith("http"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Enter a valid URL.")
    return await scrape_price(url)


@router.get("/keywords")
def admin_keywords(
    q: str = Query(..., min_length=1, description="Seed keyword/topic"),
    _: None = Depends(require_admin),
) -> dict:
    """Keyword research (Serper/DataForSEO). Returns related keywords, People-Also-Ask,
    and search volumes when providers are configured."""
    return seo_tools.keyword_research(q)


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
    if "is_featured" in payload:
        listing.is_featured = bool(payload["is_featured"])
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


@router.get("/founding-applications")
def admin_founding_applications(
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
    status_filter: str | None = Query(None, alias="status"),
) -> dict:
    stmt = select(FoundingApplication).order_by(FoundingApplication.created_at.desc())
    if status_filter:
        stmt = stmt.where(FoundingApplication.status == status_filter)
    rows = session.exec(stmt).all()
    return {
        "items": [FoundingApplicationRead(**r.model_dump()).model_dump() for r in rows],
        "count": len(rows),
    }


@router.patch("/founding-applications/{app_id}")
def admin_review_application(
    app_id: int,
    payload: dict,
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
) -> dict:
    app = session.get(FoundingApplication, app_id)
    if not app:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    new_status = payload.get("status")
    if new_status not in {"pending", "approved", "rejected"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="status must be pending|approved|rejected")

    result: dict = {"id": app.id, "status": new_status}
    if new_status == "approved" and app.status != "approved":
        # Create a founding seller from the application.
        handle = (app.handle_wanted or app.email.split("@")[0]).strip().lower()
        handle = "".join(ch for ch in handle if ch.isalnum() or ch in "_.-") or f"seller{app.id}"
        if session.exec(select(Seller).where(Seller.handle == handle)).first():
            handle = f"{handle}{app.id}"
        seller = Seller(
            handle=handle,
            display_name=app.name,
            email=app.email,
            store_edit_token=secrets.token_urlsafe(16),
        )
        grant_founding_if_available(session, seller)
        session.add(seller)
        result["seller_handle"] = handle
        result["store_edit_token"] = seller.store_edit_token
        result["is_founding"] = seller.is_founding
    app.status = new_status
    session.add(app)
    session.commit()
    return result


@router.post("/reset")
def admin_reset(
    confirm: bool = Query(False, description="Must be true to wipe data"),
    keep_applications: bool = Query(True, description="Keep Founding applications"),
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
) -> dict:
    """Danger: clears listings, sales, streams, and sellers (e.g. to remove demo
    data). Keeps Founding applications by default."""
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pass ?confirm=true to wipe data.",
        )
    deleted = {}
    models_to_clear = [("streams", LiveStream), ("sales", Sale), ("listings", Listing), ("sellers", Seller)]
    if not keep_applications:
        models_to_clear.append(("applications", FoundingApplication))
    for name, model in models_to_clear:
        rows = session.exec(select(model)).all()
        for r in rows:
            session.delete(r)
        deleted[name] = len(rows)
    session.commit()
    return {"status": "reset", "deleted": deleted}


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

"""n8n + Obsidian integration surface.

Outbound: marketplace events POST to ``N8N_WEBHOOK_URL``.
Inbound: admin-token gated endpoints for vault export, Obsidian push, and
event ping tests — so n8n can pull as well as receive.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from .. import platform_events, webhooks_out
from ..config import settings
from ..database import get_session
from ..models import Listing, Order, Seller, SupportConversation
from ..routers.admin import require_admin
from ..support import knowledge, obsidian

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


@router.get("/status")
def integrations_hub_status(_: None = Depends(require_admin)) -> dict:
    return {
        "n8n": {
            "configured": webhooks_out.n8n_configured(),
            "signed": bool(settings.n8n_webhook_secret),
        },
        "obsidian": {
            "configured": obsidian.obsidian_configured(),
            "vault_prefix": settings.obsidian_vault_prefix,
            "api_url": settings.obsidian_api_url or None,
        },
        "events": [
            "listing.created",
            "order.paid",
            "seller.applied",
            "founding.applied",
            "support.escalated",
            "knowledge.updated",
            "ops.alert",
            "integrations.test",
        ],
    }


@router.post("/events/test")
def test_n8n_webhook(payload: dict | None = None, _: None = Depends(require_admin)) -> dict:
    """Fire a synthetic event so you can verify the n8n workflow is listening."""
    data = {"hello": "ragnar", **(payload or {})}
    ok = webhooks_out.dispatch("integrations.test", data)
    return {"ok": ok, "configured": webhooks_out.n8n_configured(), "event": "integrations.test"}


@router.get("/obsidian/export")
def export_obsidian_vault(
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
) -> dict:
    """Export Counsel knowledge as Obsidian markdown files (JSON bundle)."""
    files = obsidian.export_vault(session)
    return {
        "count": len(files),
        "prefix": settings.obsidian_vault_prefix,
        "files": files,
    }


@router.post("/obsidian/sync")
def sync_obsidian_vault(
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
) -> dict:
    """Push the full knowledge vault to Obsidian Local REST API (if configured).

    Also emits ``knowledge.vault_synced`` to n8n so a workflow can write files
    even when the Local REST API is unreachable from the server.
    """
    files = obsidian.export_vault(session)
    result = obsidian.sync_vault(session)
    platform_events.emit(
        "knowledge.vault_synced",
        {"count": len(files), "paths": [f["path"] for f in files], "push": result},
    )
    # Include file bodies so an n8n workflow can Write Binary File into a vault.
    return {**result, "files": files}


@router.get("/lookup/listing/{listing_id}")
def lookup_listing(
    listing_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
) -> dict:
    listing = session.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    return {
        "id": listing.id,
        "title": listing.title,
        "price_cents": listing.price_cents,
        "status": listing.status,
        "seller_id": listing.seller_id,
        "category": listing.category,
        "image_url": listing.image_url,
    }


@router.get("/lookup/order/{order_id}")
def lookup_order(
    order_id: int,
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
) -> dict:
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return {
        "id": order.id,
        "title": order.title,
        "status": order.status,
        "price_cents": order.price_cents,
        "seller_id": order.seller_id,
        "buyer_email": order.buyer_email,
        "listing_id": order.listing_id,
    }


@router.get("/lookup/seller/{handle}")
def lookup_seller(
    handle: str,
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
) -> dict:
    seller = session.exec(select(Seller).where(Seller.handle == handle.lower())).first()
    if not seller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Seller not found")
    return {
        "id": seller.id,
        "handle": seller.handle,
        "display_name": seller.display_name,
        "is_founding": seller.is_founding,
        "email": seller.email,
    }


@router.get("/lookup/support/{public_id}")
def lookup_support(
    public_id: str,
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
) -> dict:
    conv = session.exec(
        select(SupportConversation).where(SupportConversation.public_id == public_id)
    ).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return {
        "id": conv.id,
        "public_id": conv.public_id,
        "status": conv.status,
        "intent": conv.intent,
        "channel": conv.channel,
    }

"""API v1 — unified Birdman router."""
from __future__ import annotations

from fastapi import APIRouter

from . import (
    actions,
    cards,
    content,
    listings,
    market_events,
    marketplace,
    orders,
    realtime,
    users,
)

router = APIRouter(tags=["birdman-v1"])
router.include_router(users.router)
router.include_router(content.router)
router.include_router(actions.router)
router.include_router(realtime.router)
router.include_router(marketplace.router)
router.include_router(cards.router)
router.include_router(listings.router)
router.include_router(orders.router)
router.include_router(market_events.router)

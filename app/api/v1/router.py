"""API v1 — unified Birdman router."""
from __future__ import annotations

from fastapi import APIRouter

from . import actions, content, realtime, users

router = APIRouter(tags=["birdman-v1"])
router.include_router(users.router)
router.include_router(content.router)
router.include_router(actions.router)
router.include_router(realtime.router)

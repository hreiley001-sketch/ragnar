"""Realtime / pulse endpoints — SSE-ready surface."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.services import realtime_service

router = APIRouter(prefix="/realtime", tags=["birdman-realtime"])


@router.get("/pulse")
def pulse() -> dict:
    return realtime_service.organism_pulse()


@router.get("/stream")
async def pulse_stream() -> StreamingResponse:
    """Minimal SSE heartbeat of organ health (extend for ride events later)."""

    async def gen():
        for _ in range(3):
            payload = realtime_service.organism_pulse()
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(gen(), media_type="text/event-stream")

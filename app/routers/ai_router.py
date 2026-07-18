"""AI endpoints: natural-language search parsing + description generation."""
from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from .. import ai
from ..schemas import ScanFields

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/search")
def ai_search(q: str = Query(..., min_length=1, description="Natural-language query")) -> dict:
    """Turn a natural-language request into structured storefront filters."""
    return ai.parse_search(q)


class DescribeRequest(ScanFields):
    pass


@router.post("/describe")
def ai_describe(fields: DescribeRequest) -> dict:
    return ai.generate_description(fields.model_dump())

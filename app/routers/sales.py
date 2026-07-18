"""Sold-price history / comps."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from ..comps import build_keyword, external_sold
from ..database import get_session
from ..models import Category, GradingCompany
from ..schemas import SalesHistory
from ..services import match_sales, summarize_sales

router = APIRouter(prefix="/api/sales", tags=["sales"])


@router.get("/history", response_model=SalesHistory)
def sales_history(
    session: Session = Depends(get_session),
    category: Category | None = Query(None),
    set_name: str | None = Query(None),
    card_number: str | None = Query(None),
    player_or_character: str | None = Query(None),
    graded: bool | None = Query(None),
    grading_company: GradingCompany | None = Query(None),
    grade: float | None = Query(None, ge=1, le=10),
    lookback_days: int | None = Query(None, ge=1, le=3650),
) -> SalesHistory:
    """Recent comparable sales for a card identity, aggregated.

    Draws on RAGNAR's own completed sales (plus any seeded/external comps).
    """
    sales = match_sales(
        session,
        category=category.value if category else None,
        set_name=set_name,
        card_number=card_number,
        player_or_character=player_or_character,
        is_graded=graded,
        grading_company=grading_company.value if grading_company else None,
        grade=grade,
        lookback_days=lookback_days,
    )
    external = external_sold(
        build_keyword(
            player_or_character=player_or_character,
            set_name=set_name,
            card_number=card_number,
            grading_company=grading_company.value if grading_company else None,
            grade=grade,
        )
    )
    return SalesHistory(**summarize_sales(sales, external))

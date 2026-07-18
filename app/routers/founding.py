"""Founding 250 — public application funnel."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from ..database import get_session
from ..models import FoundingApplication
from ..schemas import FoundingApplicationCreate, FoundingApplicationRead, FoundingStatus
from ..services import founding_status

router = APIRouter(prefix="/api/founding", tags=["founding"])


@router.get("/status", response_model=FoundingStatus)
def status_(session: Session = Depends(get_session)) -> FoundingStatus:
    return FoundingStatus(**founding_status(session))


@router.post("/apply", response_model=FoundingApplicationRead, status_code=status.HTTP_201_CREATED)
def apply(payload: FoundingApplicationCreate, session: Session = Depends(get_session)) -> FoundingApplicationRead:
    application = FoundingApplication(
        name=payload.name.strip(),
        email=payload.email.strip().lower(),
        handle_wanted=(payload.handle_wanted or "").strip() or None,
        categories=(payload.categories or "").strip() or None,
        current_platforms=(payload.current_platforms or "").strip() or None,
        monthly_volume=(payload.monthly_volume or "").strip() or None,
        message=(payload.message or "").strip() or None,
    )
    session.add(application)
    session.commit()
    session.refresh(application)
    return FoundingApplicationRead(**application.model_dump())

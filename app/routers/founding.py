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

    # Alert the crew (in-app for admins; email/Discord when configured).
    try:
        from ..emailer import ops_alert
        from ..notify import notify_admins
        notify_admins(
            session, "founding_application",
            f"Founding application: {application.name}",
            body=(application.categories or application.message or application.email)[:200],
            link="/admin",
        )
        ops_alert(
            f"New Founding 250 application: {application.name} ({application.email})",
            f"Sells: {application.categories or '—'} | Volume: {application.monthly_volume or '—'}",
        )
        from .. import platform_events

        platform_events.emit(
            "founding.applied",
            {
                "id": application.id,
                "name": application.name,
                "email": application.email,
                "handle_wanted": application.handle_wanted,
                "categories": application.categories,
                "monthly_volume": application.monthly_volume,
            },
        )
    except Exception:  # noqa: BLE001
        pass

    return FoundingApplicationRead(**application.model_dump())

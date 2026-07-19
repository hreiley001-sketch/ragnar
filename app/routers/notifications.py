"""In-app notifications (the bell)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlmodel import Session, select

from ..auth import require_user
from ..database import get_session
from ..models import Notification

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _to_dict(n: Notification) -> dict:
    return {"id": n.id, "type": n.type, "title": n.title, "body": n.body,
            "link": n.link, "read": n.read, "created_at": n.created_at.isoformat()}


@router.get("")
def list_notifications(
    session: Session = Depends(get_session),
    user=Depends(require_user),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    rows = session.exec(
        select(Notification).where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc()).limit(limit)
    ).all()
    return {"items": [_to_dict(n) for n in rows], "count": len(rows)}


@router.get("/unread-count")
def unread_count(session: Session = Depends(get_session), user=Depends(require_user)) -> dict:
    n = session.exec(
        select(func.count()).select_from(Notification)
        .where(Notification.user_id == user.id, Notification.read == False)  # noqa: E712
    ).one()
    return {"unread": n}


@router.post("/read-all")
def read_all(session: Session = Depends(get_session), user=Depends(require_user)) -> dict:
    rows = session.exec(
        select(Notification).where(Notification.user_id == user.id, Notification.read == False)  # noqa: E712
    ).all()
    for n in rows:
        n.read = True
        session.add(n)
    session.commit()
    return {"marked": len(rows)}


@router.post("/{notification_id}/read")
def read_one(notification_id: int, session: Session = Depends(get_session),
             user=Depends(require_user)) -> dict:
    n = session.get(Notification, notification_id)
    if not n or n.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    n.read = True
    session.add(n)
    session.commit()
    return {"status": "read"}

"""In-app notifications (the bell) + fan-out helpers.

`notify()` writes a Notification row; other modules call the helpers to reach
the right people (a user, a seller's owner, all admins). Email/Discord mirrors
happen in emailer.py where wired — in-app always works with zero config.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlmodel import Session, select

from .models import Notification, Seller, User, UserRole

logger = logging.getLogger("ragnar.notify")


def notify(
    session: Session,
    user_id: int,
    type_: str,
    title: str,
    body: str = "",
    link: str = "",
    *,
    commit: bool = True,
) -> Optional[Notification]:
    """Create an in-app notification. Never raises — notifications must not
    break the action that triggered them."""
    try:
        n = Notification(user_id=user_id, type=type_, title=title[:200],
                         body=(body or "")[:500] or None, link=(link or "")[:300] or None)
        session.add(n)
        if commit:
            session.commit()
        return n
    except Exception as exc:  # noqa: BLE001
        logger.warning("notify failed: %s", exc)
        return None


def seller_owner_user(session: Session, seller: Seller | None) -> Optional[User]:
    """The user account that operates a store (linked via user.seller_handle)."""
    if not seller:
        return None
    return session.exec(select(User).where(User.seller_handle == seller.handle)).first()


def notify_seller(session: Session, seller: Seller | None, type_: str, title: str,
                  body: str = "", link: str = "") -> None:
    owner = seller_owner_user(session, seller)
    if owner:
        notify(session, owner.id, type_, title, body, link)


def notify_admins(session: Session, type_: str, title: str, body: str = "", link: str = "") -> None:
    admins = session.exec(select(User).where(User.role == UserRole.admin.value)).all()
    for a in admins:
        notify(session, a.id, type_, title, body, link, commit=False)
    if admins:
        session.commit()
    # Fan-out to n8n ops workflow (never blocks the request path meaningfully).
    try:
        from .platform.queue import enqueue

        enqueue(
            "ops.notify",
            {
                "type": type_,
                "title": title,
                "message": body or title,
                "link": link,
                "severity": "info",
            },
            workflow="ops/notify",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("ops.notify enqueue failed: %s", exc)


def notify_followers(session: Session, seller: Seller, type_: str, title: str,
                     body: str = "", link: str = "") -> int:
    from .models import Follow  # local to avoid cycles at import time
    follows = session.exec(select(Follow).where(Follow.seller_id == seller.id)).all()
    for f in follows:
        notify(session, f.user_id, type_, title, body, link, commit=False)
    if follows:
        session.commit()
    return len(follows)

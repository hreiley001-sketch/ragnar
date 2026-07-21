"""Community groups — Reddit-style collector clubs."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..auth import get_current_user, require_user
from ..database import get_session
from ..models import CommunityGroup, GroupComment, GroupMember, GroupThread, User, utcnow

router = APIRouter(prefix="/api/groups", tags=["groups"])


def _slugify(name: str) -> str:
    raw = "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-")
    while "--" in raw:
        raw = raw.replace("--", "-")
    return (raw or "group")[:60]


def _group_dict(g: CommunityGroup, joined: bool = False) -> dict:
    return {
        "id": g.id,
        "slug": g.slug,
        "name": g.name,
        "description": g.description,
        "kind": g.kind,
        "banner_url": g.banner_url,
        "member_count": g.member_count,
        "joined": joined,
        "created_at": g.created_at.isoformat() if g.created_at else None,
    }


def _thread_dict(t: GroupThread, author: Optional[str] = None) -> dict:
    return {
        "id": t.id,
        "group_id": t.group_id,
        "title": t.title,
        "body": t.body,
        "is_poll": t.is_poll,
        "poll_options": t.poll_options or [],
        "upvotes": t.upvotes,
        "comment_count": t.comment_count,
        "ai_summary": t.ai_summary,
        "author": author or "Collector",
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


@router.get("")
def list_groups(
    kind: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = Query(40, ge=1, le=100),
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
) -> dict:
    groups = list(session.exec(select(CommunityGroup).order_by(CommunityGroup.member_count.desc())).all())
    if kind:
        groups = [g for g in groups if g.kind == kind]
    if q:
        needle = q.lower()
        groups = [g for g in groups if needle in g.name.lower() or needle in (g.description or "").lower()]

    joined_ids: set[int] = set()
    if user:
        joined_ids = {
            mid for mid in session.exec(
                select(GroupMember.group_id).where(GroupMember.user_id == user.id)
            ).all()
        }

    return {"items": [_group_dict(g, g.id in joined_ids) for g in groups[:limit]]}


@router.get("/{slug}")
def get_group(
    slug: str,
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
) -> dict:
    group = session.exec(select(CommunityGroup).where(CommunityGroup.slug == slug)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    joined = False
    if user:
        joined = session.exec(
            select(GroupMember).where(
                GroupMember.group_id == group.id, GroupMember.user_id == user.id
            )
        ).first() is not None
    threads = list(session.exec(
        select(GroupThread).where(GroupThread.group_id == group.id).order_by(GroupThread.created_at.desc()).limit(40)
    ).all())
    return {
        "group": _group_dict(group, joined),
        "threads": [_thread_dict(t) for t in threads],
    }


class CreateGroupBody(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=1000)
    kind: str = Field(default="club", max_length=40)


@router.post("")
def create_group(
    payload: CreateGroupBody,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    base = _slugify(payload.name)
    slug = base
    n = 1
    while session.exec(select(CommunityGroup).where(CommunityGroup.slug == slug)).first():
        n += 1
        slug = f"{base}-{n}"[:60]

    group = CommunityGroup(
        slug=slug,
        name=payload.name.strip(),
        description=payload.description.strip(),
        kind=payload.kind,
        member_count=1,
        created_by_user_id=user.id,
    )
    session.add(group)
    session.commit()
    session.refresh(group)
    session.add(GroupMember(group_id=group.id, user_id=user.id, role="admin"))
    session.commit()
    return _group_dict(group, True)


@router.post("/{slug}/join")
def join_group(
    slug: str,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    group = session.exec(select(CommunityGroup).where(CommunityGroup.slug == slug)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    existing = session.exec(
        select(GroupMember).where(GroupMember.group_id == group.id, GroupMember.user_id == user.id)
    ).first()
    if existing:
        return {"ok": True, "joined": True, "member_count": group.member_count}
    session.add(GroupMember(group_id=group.id, user_id=user.id))
    group.member_count = (group.member_count or 0) + 1
    session.add(group)
    session.commit()
    return {"ok": True, "joined": True, "member_count": group.member_count}


class CreateThreadBody(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    body: str = Field(min_length=1, max_length=4000)
    is_poll: bool = False
    poll_options: list[str] = Field(default_factory=list)


@router.post("/{slug}/threads")
def create_thread(
    slug: str,
    payload: CreateThreadBody,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    group = session.exec(select(CommunityGroup).where(CommunityGroup.slug == slug)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    summary = None
    if len(payload.body) > 160:
        summary = payload.body[:157].rsplit(" ", 1)[0] + "…"
    thread = GroupThread(
        group_id=group.id,
        author_user_id=user.id,
        title=payload.title.strip(),
        body=payload.body.strip(),
        is_poll=payload.is_poll,
        poll_options=payload.poll_options[:6],
        ai_summary=summary,
    )
    session.add(thread)
    session.commit()
    session.refresh(thread)
    return _thread_dict(thread, user.name or user.email.split("@")[0])


@router.post("/threads/{thread_id}/upvote")
def upvote_thread(
    thread_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    del user
    thread = session.get(GroupThread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    thread.upvotes = (thread.upvotes or 0) + 1
    session.add(thread)
    session.commit()
    return {"ok": True, "upvotes": thread.upvotes}


class CommentBody(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


@router.post("/threads/{thread_id}/comments")
def add_comment(
    thread_id: int,
    payload: CommentBody,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    thread = session.get(GroupThread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    comment = GroupComment(
        thread_id=thread.id,
        author_user_id=user.id,
        body=payload.body.strip(),
    )
    thread.comment_count = (thread.comment_count or 0) + 1
    session.add(comment)
    session.add(thread)
    session.commit()
    session.refresh(comment)
    return {
        "id": comment.id,
        "body": comment.body,
        "author": user.name or user.email.split("@")[0],
        "upvotes": comment.upvotes,
        "created_at": comment.created_at.isoformat(),
    }


@router.get("/threads/{thread_id}/comments")
def list_comments(
    thread_id: int,
    session: Session = Depends(get_session),
) -> dict:
    comments = list(session.exec(
        select(GroupComment).where(GroupComment.thread_id == thread_id).order_by(GroupComment.created_at.asc())
    ).all())
    return {
        "items": [
            {
                "id": c.id,
                "body": c.body,
                "upvotes": c.upvotes,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in comments
        ]
    }

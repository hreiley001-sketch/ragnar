"""Social feed — Instagram-style posts from sellers."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..auth import get_current_user, require_user
from ..database import get_session
from ..models import FeedPost, Follow, Listing, Seller, User, utcnow
from ..notify import notify_followers

router = APIRouter(prefix="/api/feed", tags=["feed"])


def _seller_dict(seller: Seller) -> dict:
    return {
        "id": seller.id,
        "handle": seller.handle,
        "display_name": seller.display_name,
        "avatar_url": seller.avatar_url,
        "is_founding": bool(seller.is_founding),
    }


def _post_dict(post: FeedPost, seller: Optional[Seller]) -> dict:
    return {
        "id": post.id,
        "kind": post.kind,
        "title": post.title,
        "body": post.body,
        "image_url": post.image_url,
        "listing_id": post.listing_id,
        "tags": post.tags or [],
        "market_value": (post.market_value_cents or 0) / 100.0 if post.market_value_cents else None,
        "like_count": post.like_count,
        "comment_count": post.comment_count,
        "is_story": post.is_story,
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "seller": _seller_dict(seller) if seller else None,
    }


@router.get("")
def list_feed(
    following_only: bool = Query(False),
    stories: bool = Query(False),
    limit: int = Query(30, ge=1, le=100),
    session: Session = Depends(get_session),
    user: Optional[User] = Depends(get_current_user),
) -> dict:
    q = select(FeedPost).where(FeedPost.is_story == stories).order_by(FeedPost.created_at.desc())
    posts = list(session.exec(q.limit(limit * 2)).all())

    if following_only and user:
        followed = {
            r for r in session.exec(
                select(Follow.seller_id).where(Follow.user_id == user.id)
            ).all()
        }
        posts = [p for p in posts if p.seller_id in followed]

    posts = posts[:limit]
    seller_ids = {p.seller_id for p in posts}
    sellers = {}
    if seller_ids:
        for s in session.exec(select(Seller).where(Seller.id.in_(list(seller_ids)))).all():
            sellers[s.id] = s

    return {"items": [_post_dict(p, sellers.get(p.seller_id)) for p in posts]}


class CreatePostBody(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    title: Optional[str] = Field(default=None, max_length=200)
    kind: str = Field(default="post", max_length=32)
    image_url: Optional[str] = None
    listing_id: Optional[int] = None
    tags: list[str] = Field(default_factory=list)
    is_story: bool = False
    market_value: Optional[float] = None


@router.post("")
def create_post(
    payload: CreatePostBody,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    if not user.seller_handle:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Seller account required")
    seller = session.exec(select(Seller).where(Seller.handle == user.seller_handle)).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller store not found")

    market_cents = int(round(payload.market_value * 100)) if payload.market_value else None
    if payload.listing_id and market_cents is None:
        listing = session.get(Listing, payload.listing_id)
        if listing:
            market_cents = listing.price_cents

    post = FeedPost(
        seller_id=seller.id,
        kind=payload.kind,
        title=payload.title,
        body=payload.body.strip(),
        image_url=payload.image_url,
        listing_id=payload.listing_id,
        tags=payload.tags[:12],
        market_value_cents=market_cents,
        is_story=payload.is_story,
    )
    session.add(post)
    session.commit()
    session.refresh(post)

    notify_followers(
        session, seller, "feed_post",
        f"@{seller.handle} posted",
        (payload.title or payload.body)[:120],
        f"/feed#post-{post.id}",
    )
    return _post_dict(post, seller)


@router.post("/{post_id}/like")
def like_post(
    post_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> dict:
    del user
    post = session.get(FeedPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    post.like_count = (post.like_count or 0) + 1
    session.add(post)
    session.commit()
    return {"ok": True, "like_count": post.like_count}

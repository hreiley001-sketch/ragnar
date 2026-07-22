"""User actions → queue → n8n (never wait on automation)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app import auth
from app.models import ActionRequest, ActionResult
from app.services import action_service
from app.utils.exceptions import BirdmanError

router = APIRouter(prefix="/actions", tags=["birdman-actions"])


class LikeRequest(BaseModel):
    content_id: str = Field(min_length=1, max_length=64)
    extra: dict[str, Any] = Field(default_factory=dict)


@router.post("", response_model=ActionResult, status_code=status.HTTP_202_ACCEPTED)
def post_action(
    body: ActionRequest,
    user=Depends(auth.require_user),
) -> ActionResult:
    payload = dict(body.payload or {})
    payload.setdefault("user_id", str(getattr(user, "supabase_sub", None) or user.id))
    body = ActionRequest(topic=body.topic, payload=payload, workflow=body.workflow)
    try:
        return action_service.enqueue_action(body)
    except BirdmanError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc


@router.post("/like", response_model=ActionResult, status_code=status.HTTP_202_ACCEPTED)
def post_like(
    body: LikeRequest,
    user=Depends(auth.require_user),
) -> ActionResult:
    """User like → ecosystem ripple (async). See vault User Like Ripple."""
    user_id = str(getattr(user, "supabase_sub", None) or user.id)
    try:
        return action_service.enqueue_user_action(
            user_id=user_id,
            action_type="like",
            content_id=body.content_id,
            payload=body.extra,
        )
    except BirdmanError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc

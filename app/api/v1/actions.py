"""User actions → queue → n8n (never wait on automation)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app import auth
from app.models import ActionRequest, ActionResult
from app.services import action_service
from app.utils.exceptions import BirdmanError

router = APIRouter(prefix="/actions", tags=["birdman-actions"])


@router.post("", response_model=ActionResult, status_code=status.HTTP_202_ACCEPTED)
def post_action(
    body: ActionRequest,
    user=Depends(auth.require_user),
) -> ActionResult:
    _ = user  # authenticated write surface
    try:
        return action_service.enqueue_action(body)
    except BirdmanError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc

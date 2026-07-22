"""Orders — place / history / status."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app import auth
from app.models.marketplace import OrderCreate, OrderRead, OrderStatusUpdate
from app.services import order_service, user_service
from app.utils.exceptions import BirdmanError, NotFoundError

router = APIRouter(prefix="/orders", tags=["birdman-orders"])


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
def place_order(body: OrderCreate, user=Depends(auth.require_user)) -> OrderRead:
    try:
        return order_service.place_order(user_service.actor_id(user), body)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except BirdmanError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc


@router.get("", response_model=list[OrderRead])
def my_orders(
    limit: int = Query(50, ge=1, le=100),
    user=Depends(auth.require_user),
) -> list[OrderRead]:
    return order_service.list_orders(user_service.actor_id(user), limit=limit)


@router.patch("/{order_id}", response_model=OrderRead)
def update_order(
    order_id: str,
    body: OrderStatusUpdate,
    user=Depends(auth.require_user),
) -> OrderRead:
    try:
        return order_service.update_order_status(
            order_id, body, actor_id=user_service.actor_id(user)
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
    except BirdmanError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc

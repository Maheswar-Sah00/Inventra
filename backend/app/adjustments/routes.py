from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.adjustments import services
from app.adjustments.schemas import AdjustmentCreate, AdjustmentOut, AdjustmentUpdate
from app.auth.dependencies import CurrentUser, get_current_user
from app.core.database import get_db
from app.core.pagination import Page, PageParamsDep
from app.inventory.routing import SearchFilter, StatusFilter

router = APIRouter(prefix="/adjustments", tags=["inventory adjustments"], dependencies=[Depends(get_current_user)])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=Page[AdjustmentOut])
def list_adjustments(
    db: DbSession,
    page: PageParamsDep,
    status: StatusFilter = None,
    q: SearchFilter = None,
    location_id: int | None = None,
    warehouse_id: int | None = None,
    product_id: int | None = None,
    category_id: int | None = None,
):
    return services.list_adjustments(
        db,
        page,
        statuses=status,
        q=q,
        location_id=location_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
        category_id=category_id,
    )


@router.post("", response_model=AdjustmentOut, status_code=status.HTTP_201_CREATED)
def create_adjustment(payload: AdjustmentCreate, db: DbSession, current_user: CurrentUser):
    return services.with_current_stock(db, services.create_adjustment(db, payload, current_user))


@router.get("/{adjustment_id}", response_model=AdjustmentOut)
def get_adjustment(adjustment_id: int, db: DbSession):
    return services.with_current_stock(db, services.get_adjustment(db, adjustment_id))


@router.patch("/{adjustment_id}", response_model=AdjustmentOut)
def update_adjustment(adjustment_id: int, payload: AdjustmentUpdate, db: DbSession):
    adjustment = services.update_adjustment(db, services.get_adjustment(db, adjustment_id), payload)
    return services.with_current_stock(db, adjustment)


@router.post("/{adjustment_id}/confirm", response_model=AdjustmentOut)
def confirm_adjustment(adjustment_id: int, db: DbSession):
    adjustment = services.confirm_adjustment(db, services.get_adjustment(db, adjustment_id))
    return services.with_current_stock(db, adjustment)


@router.post("/{adjustment_id}/validate", response_model=AdjustmentOut)
def validate_adjustment(adjustment_id: int, db: DbSession, current_user: CurrentUser):
    return services.validate_adjustment(db, services.get_adjustment(db, adjustment_id), current_user)


@router.post("/{adjustment_id}/cancel", response_model=AdjustmentOut)
def cancel_adjustment(adjustment_id: int, db: DbSession):
    return services.cancel_adjustment(db, services.get_adjustment(db, adjustment_id))

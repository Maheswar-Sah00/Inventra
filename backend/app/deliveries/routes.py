from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_current_user
from app.core.database import get_db
from app.core.pagination import Page, PageParamsDep
from app.deliveries import services
from app.deliveries.schemas import DeliveryCreate, DeliveryOut, DeliveryUpdate
from app.inventory.routing import SearchFilter, StatusFilter

router = APIRouter(prefix="/deliveries", tags=["delivery orders"], dependencies=[Depends(get_current_user)])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=Page[DeliveryOut])
def list_deliveries(
    db: DbSession,
    page: PageParamsDep,
    status: StatusFilter = None,
    q: SearchFilter = None,
    location_id: int | None = None,
    warehouse_id: int | None = None,
    product_id: int | None = None,
    category_id: int | None = None,
):
    return services.list_deliveries(
        db,
        page,
        statuses=status,
        q=q,
        location_id=location_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
        category_id=category_id,
    )


@router.post("", response_model=DeliveryOut, status_code=status.HTTP_201_CREATED)
def create_delivery(payload: DeliveryCreate, db: DbSession, current_user: CurrentUser):
    return services.with_availability(db, services.create_delivery(db, payload, current_user))


@router.get("/{delivery_id}", response_model=DeliveryOut)
def get_delivery(delivery_id: int, db: DbSession):
    return services.with_availability(db, services.get_delivery(db, delivery_id))


@router.patch("/{delivery_id}", response_model=DeliveryOut)
def update_delivery(delivery_id: int, payload: DeliveryUpdate, db: DbSession):
    delivery = services.update_delivery(db, services.get_delivery(db, delivery_id), payload)
    return services.with_availability(db, delivery)


@router.post("/{delivery_id}/confirm", response_model=DeliveryOut)
def confirm_delivery(delivery_id: int, db: DbSession):
    return services.with_availability(db, services.confirm_delivery(db, services.get_delivery(db, delivery_id)))


@router.post("/{delivery_id}/pick", response_model=DeliveryOut)
def pick_delivery(delivery_id: int, db: DbSession, current_user: CurrentUser):
    delivery = services.pick_delivery(db, services.get_delivery(db, delivery_id), current_user)
    return services.with_availability(db, delivery)


@router.post("/{delivery_id}/pack", response_model=DeliveryOut)
def pack_delivery(delivery_id: int, db: DbSession, current_user: CurrentUser):
    delivery = services.pack_delivery(db, services.get_delivery(db, delivery_id), current_user)
    return services.with_availability(db, delivery)


@router.post("/{delivery_id}/validate", response_model=DeliveryOut)
def validate_delivery(delivery_id: int, db: DbSession, current_user: CurrentUser):
    return services.validate_delivery(db, services.get_delivery(db, delivery_id), current_user)


@router.post("/{delivery_id}/cancel", response_model=DeliveryOut)
def cancel_delivery(delivery_id: int, db: DbSession):
    return services.cancel_delivery(db, services.get_delivery(db, delivery_id))

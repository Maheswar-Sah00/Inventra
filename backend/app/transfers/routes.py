from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_current_user
from app.core.database import get_db
from app.core.pagination import Page, PageParamsDep
from app.inventory.routing import SearchFilter, StatusFilter
from app.transfers import services
from app.transfers.schemas import TransferCreate, TransferOut, TransferUpdate

router = APIRouter(prefix="/transfers", tags=["internal transfers"], dependencies=[Depends(get_current_user)])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=Page[TransferOut])
def list_transfers(
    db: DbSession,
    page: PageParamsDep,
    status: StatusFilter = None,
    q: SearchFilter = None,
    location_id: int | None = None,
    warehouse_id: int | None = None,
    product_id: int | None = None,
    category_id: int | None = None,
):
    return services.list_transfers(
        db,
        page,
        statuses=status,
        q=q,
        location_id=location_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
        category_id=category_id,
    )


@router.post("", response_model=TransferOut, status_code=status.HTTP_201_CREATED)
def create_transfer(payload: TransferCreate, db: DbSession, current_user: CurrentUser):
    return services.with_availability(db, services.create_transfer(db, payload, current_user))


@router.get("/{transfer_id}", response_model=TransferOut)
def get_transfer(transfer_id: int, db: DbSession):
    return services.with_availability(db, services.get_transfer(db, transfer_id))


@router.patch("/{transfer_id}", response_model=TransferOut)
def update_transfer(transfer_id: int, payload: TransferUpdate, db: DbSession):
    transfer = services.update_transfer(db, services.get_transfer(db, transfer_id), payload)
    return services.with_availability(db, transfer)


@router.post("/{transfer_id}/confirm", response_model=TransferOut)
def confirm_transfer(transfer_id: int, db: DbSession):
    return services.with_availability(db, services.confirm_transfer(db, services.get_transfer(db, transfer_id)))


@router.post("/{transfer_id}/validate", response_model=TransferOut)
def validate_transfer(transfer_id: int, db: DbSession, current_user: CurrentUser):
    return services.validate_transfer(db, services.get_transfer(db, transfer_id), current_user)


@router.post("/{transfer_id}/cancel", response_model=TransferOut)
def cancel_transfer(transfer_id: int, db: DbSession):
    return services.cancel_transfer(db, services.get_transfer(db, transfer_id))

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_current_user
from app.core.database import get_db
from app.core.pagination import Page, PageParamsDep
from app.inventory.routing import SearchFilter, StatusFilter
from app.receipts import services
from app.receipts.schemas import ReceiptCreate, ReceiptOut, ReceiptUpdate

router = APIRouter(prefix="/receipts", tags=["receipts"], dependencies=[Depends(get_current_user)])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=Page[ReceiptOut])
def list_receipts(
    db: DbSession,
    page: PageParamsDep,
    status: StatusFilter = None,
    q: SearchFilter = None,
    location_id: int | None = None,
    warehouse_id: int | None = None,
    product_id: int | None = None,
    category_id: int | None = None,
):
    return services.list_receipts(
        db,
        page,
        statuses=status,
        q=q,
        location_id=location_id,
        warehouse_id=warehouse_id,
        product_id=product_id,
        category_id=category_id,
    )


@router.post("", response_model=ReceiptOut, status_code=status.HTTP_201_CREATED)
def create_receipt(payload: ReceiptCreate, db: DbSession, current_user: CurrentUser):
    return services.create_receipt(db, payload, current_user)


@router.get("/{receipt_id}", response_model=ReceiptOut)
def get_receipt(receipt_id: int, db: DbSession):
    return services.get_receipt(db, receipt_id)


@router.patch("/{receipt_id}", response_model=ReceiptOut)
def update_receipt(receipt_id: int, payload: ReceiptUpdate, db: DbSession):
    return services.update_receipt(db, services.get_receipt(db, receipt_id), payload)


@router.post("/{receipt_id}/confirm", response_model=ReceiptOut)
def confirm_receipt(receipt_id: int, db: DbSession):
    return services.confirm_receipt(db, services.get_receipt(db, receipt_id))


@router.post("/{receipt_id}/validate", response_model=ReceiptOut)
def validate_receipt(receipt_id: int, db: DbSession, current_user: CurrentUser):
    return services.validate_receipt(db, services.get_receipt(db, receipt_id), current_user)


@router.post("/{receipt_id}/cancel", response_model=ReceiptOut)
def cancel_receipt(receipt_id: int, db: DbSession):
    return services.cancel_receipt(db, services.get_receipt(db, receipt_id))

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_roles
from app.core.database import get_db
from app.core.pagination import Page, PageParamsDep
from app.users.models import UserRole
from app.warehouses import services
from app.warehouses.schemas import WarehouseCreate, WarehouseOut, WarehouseUpdate

router = APIRouter(prefix="/warehouses", tags=["warehouses"], dependencies=[Depends(get_current_user)])
ManagerOnly = [Depends(require_roles(UserRole.INVENTORY_MANAGER))]
DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=Page[WarehouseOut])
def list_warehouses(
    db: DbSession,
    page: PageParamsDep,
    q: Annotated[str | None, Query(max_length=100, description="Search by name or code")] = None,
    is_active: bool | None = None,
):
    return services.list_warehouses(db, page, q=q, is_active=is_active)


@router.post("", response_model=WarehouseOut, status_code=status.HTTP_201_CREATED, dependencies=ManagerOnly)
def create_warehouse(payload: WarehouseCreate, db: DbSession):
    return services.create_warehouse(db, payload)


@router.get("/{warehouse_id}", response_model=WarehouseOut)
def get_warehouse(warehouse_id: int, db: DbSession):
    return services.get_warehouse(db, warehouse_id)


@router.patch("/{warehouse_id}", response_model=WarehouseOut, dependencies=ManagerOnly)
def update_warehouse(warehouse_id: int, payload: WarehouseUpdate, db: DbSession):
    return services.update_warehouse(db, services.get_warehouse(db, warehouse_id), payload)


@router.delete("/{warehouse_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=ManagerOnly)
def delete_warehouse(warehouse_id: int, db: DbSession) -> Response:
    services.delete_warehouse(db, services.get_warehouse(db, warehouse_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)

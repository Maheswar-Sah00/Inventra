from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.crud import apply_changes, commit_or_conflict, delete_or_conflict, ensure_unique, get_or_404
from app.core.pagination import Page, PageParams, contains, paginate
from app.warehouses.models import Warehouse
from app.warehouses.schemas import WarehouseCreate, WarehouseOut, WarehouseUpdate

DUPLICATE_NAME = "A warehouse with this name already exists"
DUPLICATE_CODE = "A warehouse with this code already exists"


def list_warehouses(db: Session, page: PageParams, *, q: str | None, is_active: bool | None) -> Page:
    statement = select(Warehouse)
    if q:
        statement = statement.where(or_(contains(Warehouse.name, q), contains(Warehouse.code, q)))
    if is_active is not None:
        statement = statement.where(Warehouse.is_active == is_active)
    return paginate(db, statement.order_by(Warehouse.name, Warehouse.id), page, WarehouseOut)


def get_warehouse(db: Session, warehouse_id: int) -> Warehouse:
    return get_or_404(db, Warehouse, warehouse_id, "Warehouse")


def _check_unique(db: Session, changes: dict, exclude_id: int | None = None) -> None:
    if "name" in changes:
        ensure_unique(db, Warehouse.name, changes["name"], field="name", message=DUPLICATE_NAME, exclude_id=exclude_id)
    if "code" in changes:
        ensure_unique(db, Warehouse.code, changes["code"], field="code", message=DUPLICATE_CODE, exclude_id=exclude_id)


def create_warehouse(db: Session, data: WarehouseCreate) -> Warehouse:
    _check_unique(db, data.model_dump())
    warehouse = Warehouse(**data.model_dump())
    db.add(warehouse)
    commit_or_conflict(db, "code", DUPLICATE_CODE)
    db.refresh(warehouse)
    return warehouse


def update_warehouse(db: Session, warehouse: Warehouse, data: WarehouseUpdate) -> Warehouse:
    changes = data.changes()
    _check_unique(db, changes, exclude_id=warehouse.id)
    apply_changes(warehouse, changes)
    commit_or_conflict(db, "code", DUPLICATE_CODE)
    db.refresh(warehouse)
    return warehouse


def delete_warehouse(db: Session, warehouse: Warehouse) -> None:
    """Only succeeds for a warehouse without locations; otherwise deactivate it instead."""
    delete_or_conflict(db, warehouse, "warehouse")

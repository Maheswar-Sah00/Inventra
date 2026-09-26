from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.crud import apply_changes, commit_or_conflict, delete_or_conflict, ensure_unique, get_or_404
from app.core.pagination import Page, PageParams, contains, paginate
from app.units.models import UnitOfMeasure
from app.units.schemas import UnitCreate, UnitOut, UnitUpdate

DUPLICATE_NAME = "A unit with this name already exists"
DUPLICATE_SYMBOL = "A unit with this symbol already exists"


def list_units(db: Session, page: PageParams, *, q: str | None, is_active: bool | None) -> Page:
    statement = select(UnitOfMeasure)
    if q:
        statement = statement.where(or_(contains(UnitOfMeasure.name, q), contains(UnitOfMeasure.symbol, q)))
    if is_active is not None:
        statement = statement.where(UnitOfMeasure.is_active == is_active)
    return paginate(db, statement.order_by(UnitOfMeasure.name, UnitOfMeasure.id), page, UnitOut)


def get_unit(db: Session, unit_id: int) -> UnitOfMeasure:
    return get_or_404(db, UnitOfMeasure, unit_id, "Unit of measure")


def _check_unique(db: Session, changes: dict, exclude_id: int | None = None) -> None:
    if "name" in changes:
        ensure_unique(db, UnitOfMeasure.name, changes["name"], field="name", message=DUPLICATE_NAME, exclude_id=exclude_id)
    if "symbol" in changes:
        ensure_unique(
            db, UnitOfMeasure.symbol, changes["symbol"], field="symbol", message=DUPLICATE_SYMBOL, exclude_id=exclude_id
        )


def create_unit(db: Session, data: UnitCreate) -> UnitOfMeasure:
    _check_unique(db, data.model_dump())
    unit = UnitOfMeasure(**data.model_dump())
    db.add(unit)
    commit_or_conflict(db, "name", DUPLICATE_NAME)
    db.refresh(unit)
    return unit


def update_unit(db: Session, unit: UnitOfMeasure, data: UnitUpdate) -> UnitOfMeasure:
    changes = data.changes()
    _check_unique(db, changes, exclude_id=unit.id)
    apply_changes(unit, changes)
    commit_or_conflict(db, "name", DUPLICATE_NAME)
    db.refresh(unit)
    return unit


def delete_unit(db: Session, unit: UnitOfMeasure) -> None:
    delete_or_conflict(db, unit, "unit of measure")

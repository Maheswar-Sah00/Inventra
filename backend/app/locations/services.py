from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.crud import (
    apply_changes,
    commit_or_conflict,
    delete_or_conflict,
    ensure_unique,
    get_or_404,
    get_reference,
)
from app.core.errors import field_error
from app.core.pagination import Page, PageParams, contains, paginate
from app.locations.models import Location
from app.locations.schemas import LocationCreate, LocationOut, LocationUpdate
from app.warehouses.models import Warehouse

DUPLICATE_CODE = "This warehouse already has a location with this code"
DUPLICATE_NAME = "This warehouse already has a location with this name"


def list_locations(
    db: Session, page: PageParams, *, warehouse_id: int | None, q: str | None, is_active: bool | None
) -> Page:
    statement = select(Location)
    if warehouse_id is not None:
        statement = statement.where(Location.warehouse_id == warehouse_id)
    if q:
        statement = statement.where(or_(contains(Location.name, q), contains(Location.code, q)))
    if is_active is not None:
        statement = statement.where(Location.is_active == is_active)
    return paginate(db, statement.order_by(Location.warehouse_id, Location.name, Location.id), page, LocationOut)


def get_location(db: Session, location_id: int) -> Location:
    return get_or_404(db, Location, location_id, "Location")


def get_usable_location(db: Session, location_id: int, *, field: str) -> Location:
    """Location referenced by another record: must exist and be active, in an active warehouse."""
    location = get_reference(db, Location, location_id, field=field, label="Location")
    if not location.warehouse.is_active:
        raise field_error(field, "This location's warehouse is inactive")
    return location


def _check_unique(db: Session, warehouse_id: int, changes: dict, exclude_id: int | None = None) -> None:
    in_warehouse = [Location.warehouse_id == warehouse_id]
    if "code" in changes:
        ensure_unique(
            db, Location.code, changes["code"], field="code", message=DUPLICATE_CODE, exclude_id=exclude_id, where=in_warehouse
        )
    if "name" in changes:
        ensure_unique(
            db, Location.name, changes["name"], field="name", message=DUPLICATE_NAME, exclude_id=exclude_id, where=in_warehouse
        )


def create_location(db: Session, data: LocationCreate) -> Location:
    warehouse = get_reference(db, Warehouse, data.warehouse_id, field="warehouse_id", label="Warehouse")
    _check_unique(db, warehouse.id, data.model_dump())
    location = Location(**data.model_dump())
    db.add(location)
    commit_or_conflict(db, "code", DUPLICATE_CODE)
    db.refresh(location)
    return location


def update_location(db: Session, location: Location, data: LocationUpdate) -> Location:
    changes = data.changes()
    _check_unique(db, location.warehouse_id, changes, exclude_id=location.id)
    apply_changes(location, changes)
    commit_or_conflict(db, "code", DUPLICATE_CODE)
    db.refresh(location)
    return location


def delete_location(db: Session, location: Location) -> None:
    """Only succeeds when nothing references the location; otherwise deactivate it instead."""
    delete_or_conflict(db, location, "location")

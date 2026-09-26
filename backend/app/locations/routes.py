from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_roles
from app.core.database import get_db
from app.core.pagination import Page, PageParamsDep
from app.locations import services
from app.locations.schemas import LocationCreate, LocationOut, LocationUpdate
from app.users.models import UserRole

router = APIRouter(prefix="/locations", tags=["locations"], dependencies=[Depends(get_current_user)])
ManagerOnly = [Depends(require_roles(UserRole.INVENTORY_MANAGER))]
DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=Page[LocationOut])
def list_locations(
    db: DbSession,
    page: PageParamsDep,
    warehouse_id: int | None = None,
    q: Annotated[str | None, Query(max_length=100, description="Search by name or code")] = None,
    is_active: bool | None = None,
):
    return services.list_locations(db, page, warehouse_id=warehouse_id, q=q, is_active=is_active)


@router.post("", response_model=LocationOut, status_code=status.HTTP_201_CREATED, dependencies=ManagerOnly)
def create_location(payload: LocationCreate, db: DbSession):
    return services.create_location(db, payload)


@router.get("/{location_id}", response_model=LocationOut)
def get_location(location_id: int, db: DbSession):
    return services.get_location(db, location_id)


@router.patch("/{location_id}", response_model=LocationOut, dependencies=ManagerOnly)
def update_location(location_id: int, payload: LocationUpdate, db: DbSession):
    return services.update_location(db, services.get_location(db, location_id), payload)


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=ManagerOnly)
def delete_location(location_id: int, db: DbSession) -> Response:
    services.delete_location(db, services.get_location(db, location_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)

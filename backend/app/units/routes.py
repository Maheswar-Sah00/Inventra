from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_roles
from app.core.database import get_db
from app.core.pagination import Page, PageParamsDep
from app.units import services
from app.units.schemas import UnitCreate, UnitOut, UnitUpdate
from app.users.models import UserRole

router = APIRouter(prefix="/units", tags=["units of measure"], dependencies=[Depends(get_current_user)])
ManagerOnly = [Depends(require_roles(UserRole.INVENTORY_MANAGER))]
DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=Page[UnitOut])
def list_units(
    db: DbSession,
    page: PageParamsDep,
    q: Annotated[str | None, Query(max_length=100, description="Search by name or symbol")] = None,
    is_active: bool | None = None,
):
    return services.list_units(db, page, q=q, is_active=is_active)


@router.post("", response_model=UnitOut, status_code=status.HTTP_201_CREATED, dependencies=ManagerOnly)
def create_unit(payload: UnitCreate, db: DbSession):
    return services.create_unit(db, payload)


@router.get("/{unit_id}", response_model=UnitOut)
def get_unit(unit_id: int, db: DbSession):
    return services.get_unit(db, unit_id)


@router.patch("/{unit_id}", response_model=UnitOut, dependencies=ManagerOnly)
def update_unit(unit_id: int, payload: UnitUpdate, db: DbSession):
    return services.update_unit(db, services.get_unit(db, unit_id), payload)


@router.delete("/{unit_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=ManagerOnly)
def delete_unit(unit_id: int, db: DbSession) -> Response:
    services.delete_unit(db, services.get_unit(db, unit_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)

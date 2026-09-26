from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_roles
from app.categories import services
from app.categories.schemas import CategoryCreate, CategoryOut, CategoryUpdate
from app.core.database import get_db
from app.core.pagination import Page, PageParamsDep
from app.users.models import UserRole

# Any signed-in user can read; only inventory managers can change master data.
router = APIRouter(prefix="/categories", tags=["categories"], dependencies=[Depends(get_current_user)])
ManagerOnly = [Depends(require_roles(UserRole.INVENTORY_MANAGER))]
DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=Page[CategoryOut])
def list_categories(
    db: DbSession,
    page: PageParamsDep,
    q: Annotated[str | None, Query(max_length=100, description="Search by name")] = None,
    is_active: bool | None = None,
):
    return services.list_categories(db, page, q=q, is_active=is_active)


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED, dependencies=ManagerOnly)
def create_category(payload: CategoryCreate, db: DbSession):
    return services.create_category(db, payload)


@router.get("/{category_id}", response_model=CategoryOut)
def get_category(category_id: int, db: DbSession):
    return services.get_category(db, category_id)


@router.patch("/{category_id}", response_model=CategoryOut, dependencies=ManagerOnly)
def update_category(category_id: int, payload: CategoryUpdate, db: DbSession):
    return services.update_category(db, services.get_category(db, category_id), payload)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=ManagerOnly)
def delete_category(category_id: int, db: DbSession) -> Response:
    services.delete_category(db, services.get_category(db, category_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)

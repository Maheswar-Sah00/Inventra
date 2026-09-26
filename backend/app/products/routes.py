from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_current_user, require_roles
from app.core.database import get_db
from app.core.pagination import Page, PageParamsDep
from app.products import services
from app.products.schemas import ProductCreate, ProductOut, ProductUpdate
from app.users.models import UserRole

router = APIRouter(prefix="/products", tags=["products"], dependencies=[Depends(get_current_user)])
ManagerOnly = [Depends(require_roles(UserRole.INVENTORY_MANAGER))]
DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=Page[ProductOut])
def list_products(
    db: DbSession,
    page: PageParamsDep,
    q: Annotated[str | None, Query(max_length=100, description="Search by product name or SKU")] = None,
    category_id: int | None = None,
    unit_of_measure_id: int | None = None,
    is_active: bool | None = None,
):
    return services.list_products(
        db, page, q=q, category_id=category_id, unit_of_measure_id=unit_of_measure_id, is_active=is_active
    )


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED, dependencies=ManagerOnly)
def create_product(payload: ProductCreate, db: DbSession, current_user: CurrentUser):
    return services.create_product(db, payload, current_user)


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: DbSession):
    return services.get_product(db, product_id)


@router.patch("/{product_id}", response_model=ProductOut, dependencies=ManagerOnly)
def update_product(product_id: int, payload: ProductUpdate, db: DbSession):
    return services.update_product(db, services.get_product(db, product_id), payload)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=ManagerOnly)
def delete_product(product_id: int, db: DbSession) -> Response:
    services.delete_product(db, services.get_product(db, product_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)

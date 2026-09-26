from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_roles
from app.core.database import get_db
from app.core.pagination import Page, PageParamsDep
from app.reorder_rules import services
from app.reorder_rules.schemas import ReorderRuleCreate, ReorderRuleOut, ReorderRuleUpdate
from app.users.models import UserRole

router = APIRouter(prefix="/reorder-rules", tags=["reorder rules"], dependencies=[Depends(get_current_user)])
ManagerOnly = [Depends(require_roles(UserRole.INVENTORY_MANAGER))]
DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=Page[ReorderRuleOut])
def list_reorder_rules(
    db: DbSession,
    page: PageParamsDep,
    product_id: int | None = None,
    location_id: int | None = None,
    warehouse_id: int | None = None,
    is_active: bool | None = None,
):
    return services.list_reorder_rules(
        db, page, product_id=product_id, location_id=location_id, warehouse_id=warehouse_id, is_active=is_active
    )


@router.post("", response_model=ReorderRuleOut, status_code=status.HTTP_201_CREATED, dependencies=ManagerOnly)
def create_reorder_rule(payload: ReorderRuleCreate, db: DbSession):
    return services.create_reorder_rule(db, payload)


@router.get("/{rule_id}", response_model=ReorderRuleOut)
def get_reorder_rule(rule_id: int, db: DbSession):
    return services.get_reorder_rule(db, rule_id)


@router.patch("/{rule_id}", response_model=ReorderRuleOut, dependencies=ManagerOnly)
def update_reorder_rule(rule_id: int, payload: ReorderRuleUpdate, db: DbSession):
    return services.update_reorder_rule(db, services.get_reorder_rule(db, rule_id), payload)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=ManagerOnly)
def delete_reorder_rule(rule_id: int, db: DbSession) -> Response:
    services.delete_reorder_rule(db, services.get_reorder_rule(db, rule_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)

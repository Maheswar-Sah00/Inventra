from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crud import apply_changes, commit_or_conflict, get_or_404, get_reference
from app.core.errors import conflict, field_error
from app.core.pagination import Page, PageParams, paginate
from app.locations.models import Location
from app.locations.services import get_usable_location
from app.products.models import Product
from app.reorder_rules.models import ReorderRule
from app.reorder_rules.schemas import TARGET_BELOW_MINIMUM, ReorderRuleCreate, ReorderRuleOut, ReorderRuleUpdate

DUPLICATE_RULE = "This product already has a reorder rule for this location"


def list_reorder_rules(
    db: Session,
    page: PageParams,
    *,
    product_id: int | None,
    location_id: int | None,
    warehouse_id: int | None,
    is_active: bool | None,
) -> Page:
    statement = select(ReorderRule)
    if product_id is not None:
        statement = statement.where(ReorderRule.product_id == product_id)
    if location_id is not None:
        statement = statement.where(ReorderRule.location_id == location_id)
    if warehouse_id is not None:
        statement = statement.join(Location, Location.id == ReorderRule.location_id).where(
            Location.warehouse_id == warehouse_id
        )
    if is_active is not None:
        statement = statement.where(ReorderRule.is_active == is_active)
    return paginate(db, statement.order_by(ReorderRule.id), page, ReorderRuleOut)


def get_reorder_rule(db: Session, rule_id: int) -> ReorderRule:
    return get_or_404(db, ReorderRule, rule_id, "Reorder rule")


def create_reorder_rule(db: Session, data: ReorderRuleCreate) -> ReorderRule:
    get_reference(db, Product, data.product_id, field="product_id", label="Product")
    get_usable_location(db, data.location_id, field="location_id")
    existing = db.scalar(
        select(ReorderRule.id).where(
            ReorderRule.product_id == data.product_id, ReorderRule.location_id == data.location_id
        )
    )
    if existing is not None:
        raise conflict("location_id", DUPLICATE_RULE)
    rule = ReorderRule(**data.model_dump())
    db.add(rule)
    commit_or_conflict(db, "location_id", DUPLICATE_RULE)
    db.refresh(rule)
    return rule


def update_reorder_rule(db: Session, rule: ReorderRule, data: ReorderRuleUpdate) -> ReorderRule:
    changes = data.changes()
    minimum = changes.get("minimum_quantity", rule.minimum_quantity)
    target = changes.get("target_quantity", rule.target_quantity)
    if target < minimum:
        raise field_error("target_quantity", TARGET_BELOW_MINIMUM)
    apply_changes(rule, changes)
    db.commit()
    db.refresh(rule)
    return rule


def delete_reorder_rule(db: Session, rule: ReorderRule) -> None:
    db.delete(rule)
    db.commit()

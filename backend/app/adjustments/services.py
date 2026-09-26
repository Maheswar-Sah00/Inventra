from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adjustments.models import Adjustment, AdjustmentItem
from app.adjustments.schemas import AdjustmentCreate, AdjustmentOut, AdjustmentUpdate
from app.core.crud import apply_changes, get_or_404
from app.core.pagination import Page, PageParams, paginate
from app.inventory import documents
from app.inventory.documents import OPEN_STATUSES, DocumentStatus
from app.inventory.services import StockOperation, on_hand_map
from app.locations.models import Location
from app.locations.services import get_usable_location
from app.users.models import User


def list_adjustments(
    db: Session,
    page: PageParams,
    *,
    statuses: list[DocumentStatus] | None,
    q: str | None,
    location_id: int | None,
    warehouse_id: int | None,
    product_id: int | None,
    category_id: int | None,
) -> Page:
    statement = select(Adjustment)
    if location_id is not None:
        statement = statement.where(Adjustment.location_id == location_id)
    if warehouse_id is not None:
        statement = statement.join(Location, Location.id == Adjustment.location_id).where(
            Location.warehouse_id == warehouse_id
        )
    statement = documents.filter_documents(
        statement,
        Adjustment,
        AdjustmentItem.adjustment_id,
        AdjustmentItem.product_id,
        statuses=statuses,
        q=q,
        search_columns=(Adjustment.reason,),
        product_id=product_id,
        category_id=category_id,
    )
    return paginate(db, statement, page, AdjustmentOut)


def get_adjustment(db: Session, adjustment_id: int) -> Adjustment:
    return get_or_404(db, Adjustment, adjustment_id, "Adjustment")


def with_current_stock(db: Session, adjustment: Adjustment) -> Adjustment:
    """Attach the current on-hand quantity to each line while the adjustment is open."""
    if adjustment.status in OPEN_STATUSES:
        stock = on_hand_map(db, [(item.product_id, adjustment.location_id) for item in adjustment.items])
        for item in adjustment.items:
            item.current_quantity = stock[(item.product_id, adjustment.location_id)]
    return adjustment


def create_adjustment(db: Session, data: AdjustmentCreate, user: User) -> Adjustment:
    get_usable_location(db, data.location_id, field="location_id")
    documents.check_products(db, [line.product_id for line in data.items])
    adjustment = Adjustment(
        **data.model_dump(exclude={"items"}),
        created_by_id=user.id,
        items=[AdjustmentItem(product_id=line.product_id, counted_quantity=line.counted_quantity) for line in data.items],
    )
    db.add(adjustment)
    documents.assign_reference(db, adjustment)
    db.commit()
    db.refresh(adjustment)
    return adjustment


def update_adjustment(db: Session, adjustment: Adjustment, data: AdjustmentUpdate) -> Adjustment:
    changes = data.changes()
    items = changes.pop("items", None)
    documents.begin_edit(db, adjustment)
    try:
        if "location_id" in changes:
            get_usable_location(db, changes["location_id"], field="location_id")
        apply_changes(adjustment, changes)
        if items is not None:
            documents.check_products(db, [line["product_id"] for line in items])
            documents.replace_items(db, adjustment, AdjustmentItem, items)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(adjustment)
    return adjustment


def confirm_adjustment(db: Session, adjustment: Adjustment) -> Adjustment:
    return documents.set_confirmed_status(db, adjustment, DocumentStatus.READY)


def validate_adjustment(db: Session, adjustment: Adjustment, user: User) -> Adjustment:
    """Set stock to each counted quantity. Repeating it after DONE changes nothing."""
    if not documents.begin_validation(db, adjustment, user):
        return adjustment

    def apply():
        location = get_usable_location(db, adjustment.location_id, field="location_id")
        documents.check_products(db, [item.product_id for item in adjustment.items])
        operation = StockOperation(db, adjustment.document_ref, user)
        operation.lock([(item.product_id, location.id) for item in adjustment.items])
        for item in adjustment.items:
            item.recorded_quantity, item.difference = operation.set_counted(
                item.product_id, location.id, item.counted_quantity
            )

    documents.run_validation(db, adjustment, apply)
    return adjustment


def cancel_adjustment(db: Session, adjustment: Adjustment) -> Adjustment:
    return documents.cancel(db, adjustment)

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crud import apply_changes, get_or_404
from app.core.database import utcnow
from app.core.pagination import Page, PageParams, paginate
from app.deliveries.models import Delivery, DeliveryItem
from app.deliveries.schemas import DeliveryCreate, DeliveryOut, DeliveryUpdate
from app.inventory import documents
from app.inventory.documents import OPEN_STATUSES, DocumentStatus
from app.inventory.models import MovementType
from app.inventory.services import InsufficientStock, StockOperation, check_availability, on_hand_map
from app.locations.models import Location
from app.locations.services import get_usable_location
from app.users.models import User

READY = (DocumentStatus.READY,)
PICK_PACK_RESET = {"picked_at": None, "picked_by_id": None, "packed_at": None, "packed_by_id": None}


def list_deliveries(
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
    statement = select(Delivery)
    if location_id is not None:
        statement = statement.where(Delivery.source_location_id == location_id)
    if warehouse_id is not None:
        statement = statement.join(Location, Location.id == Delivery.source_location_id).where(
            Location.warehouse_id == warehouse_id
        )
    statement = documents.filter_documents(
        statement,
        Delivery,
        DeliveryItem.delivery_id,
        DeliveryItem.product_id,
        statuses=statuses,
        q=q,
        search_columns=(Delivery.customer_name,),
        product_id=product_id,
        category_id=category_id,
    )
    return paginate(db, statement, page, DeliveryOut)


def get_delivery(db: Session, delivery_id: int) -> Delivery:
    return get_or_404(db, Delivery, delivery_id, "Delivery order")


def with_availability(db: Session, delivery: Delivery) -> Delivery:
    """Attach on-hand stock at the source to each line while the order is open."""
    if delivery.status in OPEN_STATUSES:
        stock = on_hand_map(db, [(item.product_id, delivery.source_location_id) for item in delivery.items])
        for item in delivery.items:
            item.available_quantity = stock[(item.product_id, delivery.source_location_id)]
    return delivery


def _requirements(delivery: Delivery):
    return [(item.product_id, delivery.source_location_id, item.quantity) for item in delivery.items]


def create_delivery(db: Session, data: DeliveryCreate, user: User) -> Delivery:
    get_usable_location(db, data.source_location_id, field="source_location_id")
    documents.check_products(db, [line.product_id for line in data.items])
    delivery = Delivery(
        **data.model_dump(exclude={"items"}),
        created_by_id=user.id,
        items=[DeliveryItem(product_id=line.product_id, quantity=line.quantity) for line in data.items],
    )
    db.add(delivery)
    documents.assign_reference(db, delivery)
    db.commit()
    db.refresh(delivery)
    return delivery


def update_delivery(db: Session, delivery: Delivery, data: DeliveryUpdate) -> Delivery:
    """Editing returns the order to DRAFT and clears picking/packing."""
    changes = data.changes()
    items = changes.pop("items", None)
    documents.begin_edit(db, delivery, **PICK_PACK_RESET)
    try:
        if "source_location_id" in changes:
            get_usable_location(db, changes["source_location_id"], field="source_location_id")
        apply_changes(delivery, changes)
        if items is not None:
            documents.check_products(db, [line["product_id"] for line in items])
            documents.replace_items(db, delivery, DeliveryItem, items)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(delivery)
    return delivery


def confirm_delivery(db: Session, delivery: Delivery) -> Delivery:
    """READY when the source currently has enough stock for every line, otherwise WAITING.

    Confirming a WAITING order again re-checks availability.
    """
    shortages = check_availability(db, _requirements(delivery))
    return documents.set_confirmed_status(db, delivery, DocumentStatus.WAITING if shortages else DocumentStatus.READY)


def pick_delivery(db: Session, delivery: Delivery, user: User) -> Delivery:
    if delivery.picked_at is not None and delivery.status == DocumentStatus.READY:
        return delivery
    if delivery.status != DocumentStatus.READY:
        raise documents.status_conflict(delivery, "pick")
    shortages = check_availability(db, _requirements(delivery))
    if shortages:
        raise documents.shortage_conflict(InsufficientStock(shortages))
    if not documents.claim(
        db, delivery, READY, (Delivery.picked_at.is_(None),), picked_at=utcnow(), picked_by_id=user.id
    ):
        db.rollback()
        db.refresh(delivery)
        if delivery.picked_at is None or delivery.status != DocumentStatus.READY:
            raise documents.status_conflict(delivery, "pick")
        return delivery
    db.commit()
    db.refresh(delivery)
    return delivery


def pack_delivery(db: Session, delivery: Delivery, user: User) -> Delivery:
    if delivery.packed_at is not None and delivery.status == DocumentStatus.READY:
        return delivery
    if delivery.status != DocumentStatus.READY or delivery.picked_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Pick {delivery.reference} before packing it.")
    if not documents.claim(
        db,
        delivery,
        READY,
        (Delivery.picked_at.is_not(None), Delivery.packed_at.is_(None)),
        packed_at=utcnow(),
        packed_by_id=user.id,
    ):
        db.rollback()
        db.refresh(delivery)
        if delivery.packed_at is None:
            raise documents.status_conflict(delivery, "pack")
        return delivery
    db.commit()
    db.refresh(delivery)
    return delivery


def validate_delivery(db: Session, delivery: Delivery, user: User) -> Delivery:
    """Remove every line from the source location, all or nothing. Repeating it after DONE changes nothing."""
    if delivery.status == DocumentStatus.DONE:
        return delivery
    if delivery.status == DocumentStatus.READY and delivery.packed_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Pick and pack {delivery.reference} before validating it.")
    if not documents.begin_validation(db, delivery, user, allowed=READY):
        return delivery

    def apply():
        location = get_usable_location(db, delivery.source_location_id, field="source_location_id")
        documents.check_products(db, [item.product_id for item in delivery.items])
        operation = StockOperation(db, delivery.document_ref, user)
        operation.lock([(item.product_id, location.id) for item in delivery.items])
        for item in delivery.items:
            operation.remove(MovementType.DELIVERY, item.product_id, location.id, item.quantity)
        operation.raise_if_short()

    documents.run_validation(db, delivery, apply)
    return delivery


def cancel_delivery(db: Session, delivery: Delivery) -> Delivery:
    return documents.cancel(db, delivery)

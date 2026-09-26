from sqlalchemy import or_, select
from sqlalchemy.orm import Session, aliased

from app.core.crud import apply_changes, get_or_404
from app.core.errors import field_error
from app.core.pagination import Page, PageParams, paginate
from app.inventory import documents
from app.inventory.documents import OPEN_STATUSES, DocumentStatus
from app.inventory.services import StockOperation, check_availability, on_hand_map
from app.locations.models import Location
from app.locations.services import get_usable_location
from app.transfers.models import Transfer, TransferItem
from app.transfers.schemas import SAME_LOCATION, TransferCreate, TransferOut, TransferUpdate
from app.users.models import User


def list_transfers(
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
    """location_id / warehouse_id match either the source or the destination."""
    statement = select(Transfer)
    if location_id is not None:
        statement = statement.where(
            or_(Transfer.source_location_id == location_id, Transfer.destination_location_id == location_id)
        )
    if warehouse_id is not None:
        source, destination = aliased(Location), aliased(Location)
        statement = (
            statement.join(source, source.id == Transfer.source_location_id)
            .join(destination, destination.id == Transfer.destination_location_id)
            .where(or_(source.warehouse_id == warehouse_id, destination.warehouse_id == warehouse_id))
        )
    statement = documents.filter_documents(
        statement,
        Transfer,
        TransferItem.transfer_id,
        TransferItem.product_id,
        statuses=statuses,
        q=q,
        product_id=product_id,
        category_id=category_id,
    )
    return paginate(db, statement, page, TransferOut)


def get_transfer(db: Session, transfer_id: int) -> Transfer:
    return get_or_404(db, Transfer, transfer_id, "Transfer")


def with_availability(db: Session, transfer: Transfer) -> Transfer:
    if transfer.status in OPEN_STATUSES:
        stock = on_hand_map(db, [(item.product_id, transfer.source_location_id) for item in transfer.items])
        for item in transfer.items:
            item.available_quantity = stock[(item.product_id, transfer.source_location_id)]
    return transfer


def _check_locations(db: Session, source_id: int, destination_id: int) -> None:
    get_usable_location(db, source_id, field="source_location_id")
    get_usable_location(db, destination_id, field="destination_location_id")
    if source_id == destination_id:
        raise field_error("destination_location_id", SAME_LOCATION)


def create_transfer(db: Session, data: TransferCreate, user: User) -> Transfer:
    _check_locations(db, data.source_location_id, data.destination_location_id)
    documents.check_products(db, [line.product_id for line in data.items])
    transfer = Transfer(
        **data.model_dump(exclude={"items"}),
        created_by_id=user.id,
        items=[TransferItem(product_id=line.product_id, quantity=line.quantity) for line in data.items],
    )
    db.add(transfer)
    documents.assign_reference(db, transfer)
    db.commit()
    db.refresh(transfer)
    return transfer


def update_transfer(db: Session, transfer: Transfer, data: TransferUpdate) -> Transfer:
    changes = data.changes()
    items = changes.pop("items", None)
    documents.begin_edit(db, transfer)
    try:
        if "source_location_id" in changes or "destination_location_id" in changes:
            _check_locations(
                db,
                changes.get("source_location_id", transfer.source_location_id),
                changes.get("destination_location_id", transfer.destination_location_id),
            )
        apply_changes(transfer, changes)
        if items is not None:
            documents.check_products(db, [line["product_id"] for line in items])
            documents.replace_items(db, transfer, TransferItem, items)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(transfer)
    return transfer


def confirm_transfer(db: Session, transfer: Transfer) -> Transfer:
    """READY when the source currently holds enough of every line, otherwise WAITING."""
    shortages = check_availability(
        db, [(item.product_id, transfer.source_location_id, item.quantity) for item in transfer.items]
    )
    return documents.set_confirmed_status(db, transfer, DocumentStatus.WAITING if shortages else DocumentStatus.READY)


def validate_transfer(db: Session, transfer: Transfer, user: User) -> Transfer:
    """Move every line from source to destination, all or nothing. Repeating it after DONE changes nothing."""
    if not documents.begin_validation(db, transfer, user):
        return transfer

    def apply():
        _check_locations(db, transfer.source_location_id, transfer.destination_location_id)
        documents.check_products(db, [item.product_id for item in transfer.items])
        operation = StockOperation(db, transfer.document_ref, user)
        operation.lock(
            [(item.product_id, transfer.source_location_id) for item in transfer.items]
            + [(item.product_id, transfer.destination_location_id) for item in transfer.items]
        )
        for item in transfer.items:
            operation.transfer(item.product_id, transfer.source_location_id, transfer.destination_location_id, item.quantity)
        operation.raise_if_short()

    documents.run_validation(db, transfer, apply)
    return transfer


def cancel_transfer(db: Session, transfer: Transfer) -> Transfer:
    return documents.cancel(db, transfer)

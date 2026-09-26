from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crud import apply_changes, get_or_404
from app.core.pagination import Page, PageParams, paginate
from app.inventory import documents
from app.inventory.documents import DocumentStatus
from app.inventory.models import MovementType
from app.inventory.services import StockOperation
from app.locations.models import Location
from app.locations.services import get_usable_location
from app.receipts.models import Receipt, ReceiptItem
from app.receipts.schemas import ReceiptCreate, ReceiptOut, ReceiptUpdate
from app.users.models import User


def list_receipts(
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
    statement = select(Receipt)
    if location_id is not None:
        statement = statement.where(Receipt.destination_location_id == location_id)
    if warehouse_id is not None:
        statement = statement.join(Location, Location.id == Receipt.destination_location_id).where(
            Location.warehouse_id == warehouse_id
        )
    statement = documents.filter_documents(
        statement,
        Receipt,
        ReceiptItem.receipt_id,
        ReceiptItem.product_id,
        statuses=statuses,
        q=q,
        search_columns=(Receipt.supplier_name, Receipt.supplier_reference),
        product_id=product_id,
        category_id=category_id,
    )
    return paginate(db, statement, page, ReceiptOut)


def get_receipt(db: Session, receipt_id: int) -> Receipt:
    return get_or_404(db, Receipt, receipt_id, "Receipt")


def _lines(items) -> list[dict]:
    return [{"product_id": line.product_id, "quantity": line.quantity} for line in items]


def create_receipt(db: Session, data: ReceiptCreate, user: User) -> Receipt:
    get_usable_location(db, data.destination_location_id, field="destination_location_id")
    documents.check_products(db, [line.product_id for line in data.items])
    receipt = Receipt(
        **data.model_dump(exclude={"items"}),
        created_by_id=user.id,
        items=[ReceiptItem(**line) for line in _lines(data.items)],
    )
    db.add(receipt)
    documents.assign_reference(db, receipt)
    db.commit()
    db.refresh(receipt)
    return receipt


def update_receipt(db: Session, receipt: Receipt, data: ReceiptUpdate) -> Receipt:
    changes = data.changes()
    items = changes.pop("items", None)
    documents.begin_edit(db, receipt)
    try:
        if "destination_location_id" in changes:
            get_usable_location(db, changes["destination_location_id"], field="destination_location_id")
        apply_changes(receipt, changes)
        if items is not None:
            documents.check_products(db, [line["product_id"] for line in items])
            documents.replace_items(db, receipt, ReceiptItem, items)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(receipt)
    return receipt


def confirm_receipt(db: Session, receipt: Receipt) -> Receipt:
    return documents.set_confirmed_status(db, receipt, DocumentStatus.READY)


def validate_receipt(db: Session, receipt: Receipt, user: User) -> Receipt:
    """Add every line to the destination location. Repeating it after DONE changes nothing."""
    if not documents.begin_validation(db, receipt, user):
        return receipt

    def apply():
        location = get_usable_location(db, receipt.destination_location_id, field="destination_location_id")
        documents.check_products(db, [item.product_id for item in receipt.items])
        operation = StockOperation(db, receipt.document_ref, user)
        operation.lock([(item.product_id, location.id) for item in receipt.items])
        for item in receipt.items:
            operation.add(MovementType.RECEIPT, item.product_id, location.id, item.quantity)

    documents.run_validation(db, receipt, apply)
    return receipt


def cancel_receipt(db: Session, receipt: Receipt) -> Receipt:
    return documents.cancel(db, receipt)

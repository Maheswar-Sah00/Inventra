"""Read-only reporting over the other modules' tables. Nothing here stores or changes stock.

Stock status (one definition, used by the KPIs and the availability view):
  OUT_OF_STOCK  on hand == 0
  LOW_STOCK     an active reorder rule exists for the product/location and on hand <= its minimum
  IN_STOCK      otherwise
Evaluated for every active product at every position that has a stock row, plus every position with an
active reorder rule (at an active location/warehouse) even if nothing was ever stocked there.
"""

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import Select, and_, case, distinct, func, literal, or_, select, type_coerce, union
from sqlalchemy.orm import Session

from app.adjustments.models import Adjustment, AdjustmentItem
from app.categories.models import Category
from app.core.pagination import Page, PageParams, contains
from app.dashboard.schemas import (
    AppliedFilters,
    AvailabilityRow,
    DashboardSummary,
    DocumentType,
    DocumentTypeCounts,
    StockStatus,
)
from app.deliveries.models import Delivery, DeliveryItem
from app.inventory import documents
from app.inventory.documents import OPEN_STATUSES, DocumentStatus
from app.inventory.models import Stock
from app.locations.models import Location
from app.products.models import QUANTITY_TYPE, Product
from app.receipts.models import Receipt, ReceiptItem
from app.reorder_rules.models import ReorderRule
from app.transfers.models import Transfer, TransferItem
from app.warehouses.models import Warehouse


def query_error(field: str, message: str) -> HTTPException:
    return HTTPException(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=[{"loc": ["query", field], "msg": message, "type": "value_error"}],
    )


def validate_scope(db: Session, filters: AppliedFilters) -> None:
    """Unknown IDs are errors, not silently empty results."""
    if filters.warehouse_id is not None and db.get(Warehouse, filters.warehouse_id) is None:
        raise query_error("warehouse_id", "Warehouse not found")
    if filters.location_id is not None:
        location = db.get(Location, filters.location_id)
        if location is None:
            raise query_error("location_id", "Location not found")
        if filters.warehouse_id is not None and location.warehouse_id != filters.warehouse_id:
            raise query_error("location_id", "Location does not belong to the selected warehouse")
    if filters.category_id is not None and db.get(Category, filters.category_id) is None:
        raise query_error("category_id", "Category not found")


# --- Stock availability -------------------------------------------------------------------------


@dataclass
class _Availability:
    statement: Select
    quantity: object
    status: object


def _availability(filters: AppliedFilters, *, product_id: int | None = None, q: str | None = None) -> _Availability:
    stock_positions = select(Stock.product_id, Stock.location_id)
    rule_positions = (
        select(ReorderRule.product_id, ReorderRule.location_id)
        .join(Location, Location.id == ReorderRule.location_id)
        .join(Warehouse, Warehouse.id == Location.warehouse_id)
        .where(ReorderRule.is_active, Location.is_active, Warehouse.is_active)
    )
    positions = union(stock_positions, rule_positions).subquery("positions")

    quantity = type_coerce(func.coalesce(Stock.quantity, literal(0)), QUANTITY_TYPE)
    stock_status = case(
        (quantity <= 0, StockStatus.OUT_OF_STOCK.value),
        (and_(ReorderRule.id.is_not(None), quantity <= ReorderRule.minimum_quantity), StockStatus.LOW_STOCK.value),
        else_=StockStatus.IN_STOCK.value,
    )
    statement = (
        select(Product, Location, quantity.label("quantity"), ReorderRule.minimum_quantity, ReorderRule.target_quantity,
               stock_status.label("status"))
        .select_from(positions)
        .join(Product, Product.id == positions.c.product_id)
        .join(Location, Location.id == positions.c.location_id)
        .join(Warehouse, Warehouse.id == Location.warehouse_id)
        .outerjoin(Stock, and_(Stock.product_id == positions.c.product_id, Stock.location_id == positions.c.location_id))
        .outerjoin(
            ReorderRule,
            and_(
                ReorderRule.product_id == positions.c.product_id,
                ReorderRule.location_id == positions.c.location_id,
                ReorderRule.is_active,
                Location.is_active,
                Warehouse.is_active,
            ),
        )
        .where(Product.is_active)
    )
    if filters.warehouse_id is not None:
        statement = statement.where(Location.warehouse_id == filters.warehouse_id)
    if filters.location_id is not None:
        statement = statement.where(Location.id == filters.location_id)
    if filters.category_id is not None:
        statement = statement.where(Product.category_id == filters.category_id)
    if product_id is not None:
        statement = statement.where(Product.id == product_id)
    if q:
        statement = statement.where(or_(contains(Product.name, q), contains(Product.sku, q)))
    return _Availability(statement, quantity, stock_status)


def list_availability(
    db: Session,
    page: PageParams,
    filters: AppliedFilters,
    *,
    statuses: list[StockStatus] | None,
    product_id: int | None,
    q: str | None,
) -> Page:
    validate_scope(db, filters)
    availability = _availability(filters, product_id=product_id, q=q)
    statement = availability.statement
    if statuses:
        statement = statement.where(availability.status.in_([s.value for s in statuses]))

    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    severity = case(
        (availability.status == StockStatus.OUT_OF_STOCK.value, 0),
        (availability.status == StockStatus.LOW_STOCK.value, 1),
        else_=2,
    )
    rows = db.execute(
        statement.order_by(severity, Product.name, Warehouse.name, Location.name).limit(page.limit).offset(page.offset)
    ).unique()
    items = [
        AvailabilityRow(
            product=product,
            category=product.category,
            location=location,
            quantity=quantity,
            minimum_quantity=minimum,
            target_quantity=target,
            status=row_status,
        )
        for product, location, quantity, minimum, target, row_status in rows
    ]
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


# --- Documents ----------------------------------------------------------------------------------

# (model, item document column, item product column, location columns used by location/warehouse filters)
DOCUMENT_TABLES = {
    DocumentType.RECEIPT: (Receipt, ReceiptItem.receipt_id, ReceiptItem.product_id, (Receipt.destination_location_id,)),
    DocumentType.DELIVERY: (Delivery, DeliveryItem.delivery_id, DeliveryItem.product_id, (Delivery.source_location_id,)),
    DocumentType.TRANSFER: (
        Transfer,
        TransferItem.transfer_id,
        TransferItem.product_id,
        (Transfer.source_location_id, Transfer.destination_location_id),
    ),
    DocumentType.ADJUSTMENT: (Adjustment, AdjustmentItem.adjustment_id, AdjustmentItem.product_id, (Adjustment.location_id,)),
}


def _document_counts(db: Session, document_type: DocumentType, filters: AppliedFilters) -> dict[DocumentStatus, int]:
    model, item_document, item_product, location_columns = DOCUMENT_TABLES[document_type]
    statement = select(model.status, func.count(model.id)).select_from(model)
    if filters.location_id is not None:
        statement = statement.where(or_(*(column == filters.location_id for column in location_columns)))
    if filters.warehouse_id is not None:
        in_warehouse = select(Location.id).where(Location.warehouse_id == filters.warehouse_id)
        statement = statement.where(or_(*(column.in_(in_warehouse) for column in location_columns)))
    # Reuse the inventory module's document filters (status and "has a line in this category").
    statement = documents.filter_documents(
        statement,
        model,
        item_document,
        item_product,
        statuses=[filters.status] if filters.status else None,
        q=None,
        product_id=None,
        category_id=filters.category_id,
    )
    rows = db.execute(statement.order_by(None).group_by(model.status)).all()
    found = {row_status: count for row_status, count in rows}
    shown = [filters.status] if filters.status else list(DocumentStatus)
    return {s: found.get(s, 0) for s in shown}


# --- Summary ------------------------------------------------------------------------------------


def summary(db: Session, filters: AppliedFilters) -> DashboardSummary:
    validate_scope(db, filters)

    in_stock = (
        select(func.count(distinct(Stock.product_id)))
        .select_from(Stock)
        .join(Product, Product.id == Stock.product_id)
        .join(Location, Location.id == Stock.location_id)
        .where(Stock.quantity > 0, Product.is_active)
    )
    if filters.warehouse_id is not None:
        in_stock = in_stock.where(Location.warehouse_id == filters.warehouse_id)
    if filters.location_id is not None:
        in_stock = in_stock.where(Location.id == filters.location_id)
    if filters.category_id is not None:
        in_stock = in_stock.where(Product.category_id == filters.category_id)

    availability = _availability(filters).statement.subquery()
    by_status = dict(db.execute(select(availability.c.status, func.count()).group_by(availability.c.status)).all())

    # Operation KPIs count "pending" documents, or exactly the filtered status when one is chosen.
    counted = [filters.status] if filters.status else list(OPEN_STATUSES)
    types = [filters.document_type] if filters.document_type else list(DocumentType)
    breakdown = []
    kpi: dict[DocumentType, int] = {}
    for document_type in types:
        counts = _document_counts(db, document_type, filters)
        breakdown.append(DocumentTypeCounts(document_type=document_type, counts=counts, total=sum(counts.values())))
        kpi[document_type] = sum(counts.get(s, 0) for s in counted)

    return DashboardSummary(
        total_products_in_stock=db.scalar(in_stock) or 0,
        low_stock_items=by_status.get(StockStatus.LOW_STOCK.value, 0),
        out_of_stock_items=by_status.get(StockStatus.OUT_OF_STOCK.value, 0),
        pending_receipts=kpi.get(DocumentType.RECEIPT),
        pending_deliveries=kpi.get(DocumentType.DELIVERY),
        scheduled_transfers=kpi.get(DocumentType.TRANSFER),
        counted_statuses=counted,
        documents=breakdown,
        filters=filters,
    )

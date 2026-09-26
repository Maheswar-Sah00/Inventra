"""Read-only stock queries: current stock, per-product availability, reorder status and the ledger."""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.core.crud import get_or_404
from app.core.pagination import Page, PageParams, contains, paginate
from app.inventory.models import MovementType, Stock, StockMovement
from app.inventory.schemas import (
    LocationQuantity,
    MovementOut,
    ProductStockOut,
    ReorderStatusOut,
    StockOut,
)
from app.locations.models import Location
from app.products.models import Product
from app.reorder_rules.models import ReorderRule
from app.warehouses.models import Warehouse

ZERO = Decimal("0")


def list_stock(
    db: Session,
    page: PageParams,
    *,
    product_id: int | None,
    location_id: int | None,
    warehouse_id: int | None,
    category_id: int | None,
    q: str | None,
    include_empty: bool,
) -> Page:
    statement = (
        select(Stock)
        .join(Product, Product.id == Stock.product_id)
        .join(Location, Location.id == Stock.location_id)
        .join(Warehouse, Warehouse.id == Location.warehouse_id)
    )
    if not include_empty:
        statement = statement.where(Stock.quantity > 0)
    if product_id is not None:
        statement = statement.where(Stock.product_id == product_id)
    if location_id is not None:
        statement = statement.where(Stock.location_id == location_id)
    if warehouse_id is not None:
        statement = statement.where(Location.warehouse_id == warehouse_id)
    if category_id is not None:
        statement = statement.where(Product.category_id == category_id)
    if q:
        statement = statement.where(or_(contains(Product.name, q), contains(Product.sku, q)))
    statement = statement.order_by(Product.name, Warehouse.name, Location.name, Stock.id)
    return paginate(db, statement, page, StockOut)


def product_stock(db: Session, product_id: int, warehouse_id: int | None = None) -> ProductStockOut:
    product = get_or_404(db, Product, product_id, "Product")
    statement = (
        select(Stock)
        .join(Location, Location.id == Stock.location_id)
        .join(Warehouse, Warehouse.id == Location.warehouse_id)
        .where(Stock.product_id == product_id, Stock.quantity > 0)
        .order_by(Warehouse.name, Location.name)
    )
    if warehouse_id is not None:
        statement = statement.where(Location.warehouse_id == warehouse_id)
    rows = db.scalars(statement).unique().all()
    return ProductStockOut(
        product=product,
        total_quantity=sum((row.quantity for row in rows), ZERO),
        locations=[LocationQuantity(location=row.location, quantity=row.quantity) for row in rows],
    )


def reorder_status(
    db: Session,
    page: PageParams,
    *,
    product_id: int | None,
    location_id: int | None,
    warehouse_id: int | None,
    needs_reorder: bool | None,
) -> Page:
    """Active reorder rules (with active product and usable location) against current stock."""
    on_hand = func.coalesce(Stock.quantity, 0)
    statement = (
        select(ReorderRule, on_hand.label("on_hand"))
        .join(Product, Product.id == ReorderRule.product_id)
        .join(Location, Location.id == ReorderRule.location_id)
        .join(Warehouse, Warehouse.id == Location.warehouse_id)
        .outerjoin(
            Stock, and_(Stock.product_id == ReorderRule.product_id, Stock.location_id == ReorderRule.location_id)
        )
        .where(ReorderRule.is_active, Product.is_active, Location.is_active, Warehouse.is_active)
    )
    if product_id is not None:
        statement = statement.where(ReorderRule.product_id == product_id)
    if location_id is not None:
        statement = statement.where(ReorderRule.location_id == location_id)
    if warehouse_id is not None:
        statement = statement.where(Location.warehouse_id == warehouse_id)
    if needs_reorder is not None:
        low = on_hand <= ReorderRule.minimum_quantity
        statement = statement.where(low if needs_reorder else ~low)

    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = db.execute(
        statement.order_by(Product.name, Warehouse.name, Location.name, ReorderRule.id)
        .limit(page.limit)
        .offset(page.offset)
    ).unique()
    items = []
    for rule, quantity in rows:
        quantity = Decimal(str(quantity)).quantize(Decimal("0.001"))
        low = quantity <= rule.minimum_quantity
        items.append(
            ReorderStatusOut(
                rule_id=rule.id,
                product=rule.product,
                location=rule.location,
                minimum_quantity=rule.minimum_quantity,
                target_quantity=rule.target_quantity,
                on_hand=quantity,
                needs_reorder=low,
                suggested_quantity=max(rule.target_quantity - quantity, ZERO) if low else ZERO,
            )
        )
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


def list_movements(
    db: Session,
    page: PageParams,
    *,
    product_id: int | None,
    location_id: int | None,
    warehouse_id: int | None,
    category_id: int | None,
    movement_types: list[MovementType] | None,
    reference_type: str | None,
    reference_id: int | None,
    date_from: date | None,
    date_to: date | None,
    q: str | None,
) -> Page:
    """Ledger, newest first. Location/warehouse filters match either side of a movement."""
    statement = select(StockMovement)
    if product_id is not None:
        statement = statement.where(StockMovement.product_id == product_id)
    if location_id is not None:
        statement = statement.where(
            or_(StockMovement.source_location_id == location_id, StockMovement.destination_location_id == location_id)
        )
    if warehouse_id is not None:
        source, destination = aliased(Location), aliased(Location)
        statement = (
            statement.outerjoin(source, source.id == StockMovement.source_location_id)
            .outerjoin(destination, destination.id == StockMovement.destination_location_id)
            .where(or_(source.warehouse_id == warehouse_id, destination.warehouse_id == warehouse_id))
        )
    if category_id is not None or q:
        statement = statement.join(Product, Product.id == StockMovement.product_id)
        if category_id is not None:
            statement = statement.where(Product.category_id == category_id)
        if q:
            statement = statement.where(
                or_(contains(Product.name, q), contains(Product.sku, q), contains(StockMovement.reference_number, q))
            )
    if movement_types:
        statement = statement.where(StockMovement.movement_type.in_(movement_types))
    if reference_type:
        statement = statement.where(StockMovement.reference_type == reference_type.upper())
    if reference_id is not None:
        statement = statement.where(StockMovement.reference_id == reference_id)
    if date_from is not None:
        statement = statement.where(StockMovement.created_at >= datetime.combine(date_from, time.min, timezone.utc))
    if date_to is not None:
        end = datetime.combine(date_to + timedelta(days=1), time.min, timezone.utc)
        statement = statement.where(StockMovement.created_at < end)
    statement = statement.order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
    return paginate(db, statement, page, MovementOut)

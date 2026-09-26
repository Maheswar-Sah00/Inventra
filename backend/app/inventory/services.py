"""The stock engine: the only code that changes stock quantities.

Every change goes through StockOperation, which updates the `stock` row and writes the matching
`stock_movements` row in the caller's database transaction. Callers commit once at the end (or roll
back on any error), so stock and movements can never disagree.

Concurrency: StockOperation.lock() takes row locks (SELECT ... FOR UPDATE) on every stock position a
document touches, in a fixed (product_id, location_id) order to avoid deadlocks, before any quantity
is read for a decision. On SQLite, which ignores FOR UPDATE, the document's status UPDATE (always the
first write, see app.inventory.documents) already holds the database write lock, which serialises
stock changes the same way.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.inventory.models import MovementType, Stock, StockMovement
from app.locations.models import Location
from app.products.events import on_initial_stock
from app.products.models import Product
from app.users.models import User

ZERO = Decimal("0")
Position = tuple[int, int]  # (product_id, location_id)


@dataclass(frozen=True)
class DocumentRef:
    """What caused a movement: e.g. DocumentRef("RECEIPT", 12, "REC-000012")."""

    type: str
    id: int
    number: str


@dataclass(frozen=True)
class Shortage:
    product_sku: str
    location_label: str
    available: Decimal
    requested: Decimal

    def __str__(self) -> str:
        return (
            f"{self.product_sku} at {self.location_label} "
            f"(available {_fmt(self.available)}, requested {_fmt(self.requested)})"
        )


class InsufficientStock(Exception):
    def __init__(self, shortages: list[Shortage]):
        self.shortages = shortages
        super().__init__("Not enough stock: " + "; ".join(str(s) for s in shortages))


def _fmt(value: Decimal) -> str:
    return format(value.normalize(), "f")


def location_label(location: Location) -> str:
    return f"{location.warehouse.code} / {location.name}"


def _insert_statement(db: Session):
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:  # pragma: no cover - only PostgreSQL and SQLite are supported
        raise NotImplementedError(f"Unsupported database dialect: {dialect}")
    return insert(Stock)


def _ensure_position(db: Session, product_id: int, location_id: int) -> None:
    """Create an empty stock row if missing; safe when two transactions race to create it."""
    statement = (
        _insert_statement(db)
        .values(product_id=product_id, location_id=location_id, quantity=ZERO)
        .on_conflict_do_nothing(index_elements=["product_id", "location_id"])
    )
    db.execute(statement)


def on_hand(db: Session, product_id: int, location_id: int) -> Decimal:
    """Current quantity without locking (for display and availability hints, not for decisions)."""
    quantity = db.scalar(
        select(Stock.quantity).where(Stock.product_id == product_id, Stock.location_id == location_id)
    )
    return quantity if quantity is not None else ZERO


def on_hand_map(db: Session, positions: Iterable[Position]) -> dict[Position, Decimal]:
    return {position: on_hand(db, *position) for position in set(positions)}


def check_availability(db: Session, requirements: Iterable[tuple[int, int, Decimal]]) -> list[Shortage]:
    """Unlocked check of (product_id, location_id, quantity) requirements, for confirm/pick feedback.

    Not a guarantee: stock is not reserved. Validation re-checks under lock.
    """
    shortages = []
    for product_id, location_id, quantity in requirements:
        available = on_hand(db, product_id, location_id)
        if available < quantity:
            product = db.get(Product, product_id)
            location = db.get(Location, location_id)
            shortages.append(Shortage(product.sku, location_label(location), available, quantity))
    return shortages


@dataclass
class StockOperation:
    """Applies the stock changes of one document inside the caller's transaction."""

    db: Session
    reference: DocumentRef
    performed_by: User
    _rows: dict[Position, Stock] = field(default_factory=dict)
    shortages: list[Shortage] = field(default_factory=list)

    def lock(self, positions: Iterable[Position]) -> None:
        """Lock (creating if needed) every position this operation will touch, in a fixed order."""
        for product_id, location_id in sorted(set(positions)):
            _ensure_position(self.db, product_id, location_id)
            row = self.db.scalar(
                select(Stock)
                .where(Stock.product_id == product_id, Stock.location_id == location_id)
                .with_for_update(of=Stock)
                .execution_options(populate_existing=True)
            )
            self._rows[(product_id, location_id)] = row

    def _row(self, product_id: int, location_id: int) -> Stock:
        try:
            return self._rows[(product_id, location_id)]
        except KeyError:
            raise RuntimeError("Stock position was not locked before being changed") from None

    def _record(self, movement_type: MovementType, product_id: int, quantity: Decimal, source: int | None, destination: int | None):
        self.db.add(
            StockMovement(
                product_id=product_id,
                movement_type=movement_type,
                quantity=quantity,
                source_location_id=source,
                destination_location_id=destination,
                reference_type=self.reference.type,
                reference_id=self.reference.id,
                reference_number=self.reference.number,
                performed_by_id=self.performed_by.id,
            )
        )

    def _take(self, product_id: int, location_id: int, quantity: Decimal) -> bool:
        row = self._row(product_id, location_id)
        if row.quantity < quantity:
            self.shortages.append(Shortage(row.product.sku, location_label(row.location), row.quantity, quantity))
            return False
        row.quantity = row.quantity - quantity
        return True

    def add(self, movement_type: MovementType, product_id: int, location_id: int, quantity: Decimal) -> None:
        """Stock enters a location from outside (receipt, initial stock)."""
        row = self._row(product_id, location_id)
        row.quantity = row.quantity + quantity
        self._record(movement_type, product_id, quantity, None, location_id)

    def remove(self, movement_type: MovementType, product_id: int, location_id: int, quantity: Decimal) -> None:
        """Stock leaves the company from a location (delivery). Shortages are collected, not applied."""
        if self._take(product_id, location_id, quantity):
            self._record(movement_type, product_id, -quantity, location_id, None)

    def transfer(self, product_id: int, source_id: int, destination_id: int, quantity: Decimal) -> None:
        """Stock moves between two locations; total on-hand stock is unchanged."""
        if self._take(product_id, source_id, quantity):
            destination = self._row(product_id, destination_id)
            destination.quantity = destination.quantity + quantity
            self._record(MovementType.TRANSFER, product_id, quantity, source_id, destination_id)

    def set_counted(self, product_id: int, location_id: int, counted: Decimal) -> tuple[Decimal, Decimal]:
        """Set stock to a physical count. Returns (recorded quantity before, difference)."""
        row = self._row(product_id, location_id)
        recorded = row.quantity
        difference = counted - recorded
        if difference != ZERO:
            row.quantity = counted
            if difference > ZERO:
                self._record(MovementType.ADJUSTMENT, product_id, difference, None, location_id)
            else:
                self._record(MovementType.ADJUSTMENT, product_id, difference, location_id, None)
        return recorded, difference

    def raise_if_short(self) -> None:
        if self.shortages:
            raise InsufficientStock(self.shortages)


@on_initial_stock
def record_initial_stock(db: Session, product: Product, created_by: User) -> None:
    """Turns a new product's initial stock into real stock plus an INITIAL_STOCK movement."""
    operation = StockOperation(db, DocumentRef("PRODUCT", product.id, product.sku), created_by)
    operation.lock([(product.id, product.initial_location_id)])
    operation.add(MovementType.INITIAL_STOCK, product.id, product.initial_location_id, product.initial_stock)

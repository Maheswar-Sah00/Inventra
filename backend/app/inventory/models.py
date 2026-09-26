import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, utcnow
from app.locations.models import Location
from app.products.models import QUANTITY_TYPE, Product
from app.users.models import User


class MovementType(str, enum.Enum):
    INITIAL_STOCK = "INITIAL_STOCK"  # opening balance entered when a product was created
    RECEIPT = "RECEIPT"
    DELIVERY = "DELIVERY"
    TRANSFER = "TRANSFER"
    ADJUSTMENT = "ADJUSTMENT"


class Stock(TimestampMixin, Base):
    """The single authoritative on-hand quantity of one product at one location.

    Only app.inventory.services changes this table, always together with a StockMovement.
    """

    __tablename__ = "stock"
    __table_args__ = (
        UniqueConstraint("product_id", "location_id", name="uq_stock_product_id_location_id"),
        CheckConstraint("quantity >= 0", name="quantity_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True, nullable=False)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), index=True, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(QUANTITY_TYPE, default=Decimal("0"), nullable=False)

    product: Mapped[Product] = relationship(lazy="joined")
    location: Mapped[Location] = relationship(lazy="joined")


class StockMovement(Base):
    """Immutable audit record of one stock change (the stock ledger).

    `quantity` is signed as seen from total on-hand stock: positive when stock enters (receipt, initial
    stock, positive adjustment), negative when it leaves (delivery, negative adjustment). Transfers record
    the moved amount as positive. Per-location effect: -|quantity| at source_location_id and
    +|quantity| at destination_location_id.
    """

    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint("quantity <> 0", name="quantity_not_zero"),
        CheckConstraint(
            "source_location_id IS NOT NULL OR destination_location_id IS NOT NULL", name="has_location"
        ),
        Index("ix_stock_movements_reference", "reference_type", "reference_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True, nullable=False)
    movement_type: Mapped[MovementType] = mapped_column(
        Enum(MovementType, name="movement_type", native_enum=False, length=20), index=True, nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(QUANTITY_TYPE, nullable=False)
    source_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), index=True, nullable=True
    )
    destination_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), index=True, nullable=True
    )
    # The document that caused the movement, e.g. ("RECEIPT", 12, "REC-000012") or ("PRODUCT", 5, "<SKU>").
    reference_type: Mapped[str] = mapped_column(String(20), nullable=False)
    reference_id: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_number: Mapped[str] = mapped_column(String(64), nullable=False)
    performed_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)

    product: Mapped[Product] = relationship(lazy="joined")
    source_location: Mapped[Location | None] = relationship(foreign_keys=[source_location_id], lazy="joined")
    destination_location: Mapped[Location | None] = relationship(foreign_keys=[destination_location_id], lazy="joined")
    performed_by: Mapped[User] = relationship(lazy="joined")

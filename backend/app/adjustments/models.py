from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.inventory.documents import DocumentMixin
from app.locations.models import Location
from app.products.models import QUANTITY_TYPE, Product


class Adjustment(DocumentMixin, Base):
    """Physical count at one location. Validating it sets stock to the counted quantities."""

    __tablename__ = "adjustments"
    REFERENCE_PREFIX = "ADJ"
    LABEL = "adjustment"
    MOVEMENT_REFERENCE_TYPE = "ADJUSTMENT"

    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), index=True, nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)

    location: Mapped[Location] = relationship(lazy="joined")
    items: Mapped[list["AdjustmentItem"]] = relationship(
        cascade="all, delete-orphan", order_by="AdjustmentItem.id", lazy="selectin"
    )


class AdjustmentItem(Base):
    __tablename__ = "adjustment_items"
    __table_args__ = (
        UniqueConstraint("adjustment_id", "product_id", name="uq_adjustment_items_adjustment_id_product_id"),
        CheckConstraint("counted_quantity >= 0", name="counted_quantity_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    adjustment_id: Mapped[int] = mapped_column(ForeignKey("adjustments.id", ondelete="CASCADE"), index=True, nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True, nullable=False)
    counted_quantity: Mapped[Decimal] = mapped_column(QUANTITY_TYPE, nullable=False)
    # Captured under lock at validation: stock before the adjustment and counted - recorded.
    recorded_quantity: Mapped[Decimal | None] = mapped_column(QUANTITY_TYPE, nullable=True)
    difference: Mapped[Decimal | None] = mapped_column(QUANTITY_TYPE, nullable=True)

    product: Mapped[Product] = relationship(lazy="joined")

    # Filled for display on the detail endpoint (current on-hand) while open; not stored.
    current_quantity = None

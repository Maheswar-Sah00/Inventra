from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.inventory.documents import DocumentMixin
from app.locations.models import Location
from app.products.models import QUANTITY_TYPE, Product


class Transfer(DocumentMixin, Base):
    """Moves stock between two locations (same or different warehouses). Total stock is unchanged."""

    __tablename__ = "transfers"
    __table_args__ = (CheckConstraint("source_location_id <> destination_location_id", name="distinct_locations"),)
    REFERENCE_PREFIX = "TRF"
    LABEL = "transfer"
    MOVEMENT_REFERENCE_TYPE = "TRANSFER"

    source_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), index=True, nullable=False)
    destination_location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), index=True, nullable=False
    )

    source_location: Mapped[Location] = relationship(foreign_keys=[source_location_id], lazy="joined")
    destination_location: Mapped[Location] = relationship(foreign_keys=[destination_location_id], lazy="joined")
    items: Mapped[list["TransferItem"]] = relationship(
        cascade="all, delete-orphan", order_by="TransferItem.id", lazy="selectin"
    )


class TransferItem(Base):
    __tablename__ = "transfer_items"
    __table_args__ = (
        UniqueConstraint("transfer_id", "product_id", name="uq_transfer_items_transfer_id_product_id"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transfer_id: Mapped[int] = mapped_column(ForeignKey("transfers.id", ondelete="CASCADE"), index=True, nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(QUANTITY_TYPE, nullable=False)

    product: Mapped[Product] = relationship(lazy="joined")

    # Filled for display on the detail endpoint (on-hand at the source); not stored.
    available_quantity = None

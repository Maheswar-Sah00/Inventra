from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.inventory.documents import DocumentMixin
from app.locations.models import Location
from app.products.models import QUANTITY_TYPE, Product


class Receipt(DocumentMixin, Base):
    """Incoming goods from a supplier. Validating it adds the quantities to the destination location."""

    __tablename__ = "receipts"
    REFERENCE_PREFIX = "REC"
    LABEL = "receipt"
    MOVEMENT_REFERENCE_TYPE = "RECEIPT"

    supplier_name: Mapped[str] = mapped_column(String(100), nullable=False)
    supplier_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    destination_location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), index=True, nullable=False
    )

    destination_location: Mapped[Location] = relationship(lazy="joined")
    items: Mapped[list["ReceiptItem"]] = relationship(
        cascade="all, delete-orphan", order_by="ReceiptItem.id", lazy="selectin"
    )


class ReceiptItem(Base):
    __tablename__ = "receipt_items"
    __table_args__ = (
        UniqueConstraint("receipt_id", "product_id", name="uq_receipt_items_receipt_id_product_id"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("receipts.id", ondelete="CASCADE"), index=True, nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(QUANTITY_TYPE, nullable=False)

    product: Mapped[Product] = relationship(lazy="joined")

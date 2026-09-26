from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.inventory.documents import DocumentMixin
from app.locations.models import Location
from app.products.models import QUANTITY_TYPE, Product
from app.users.models import User


class Delivery(DocumentMixin, Base):
    """Outgoing goods to a customer: confirm -> pick -> pack -> validate (stock decreases on validate)."""

    __tablename__ = "deliveries"
    REFERENCE_PREFIX = "DEL"
    LABEL = "delivery order"
    MOVEMENT_REFERENCE_TYPE = "DELIVERY"

    customer_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), index=True, nullable=False)
    # Pick and pack are preparation steps while the order is READY; they do not change stock.
    picked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    picked_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    packed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    packed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)

    source_location: Mapped[Location] = relationship(lazy="joined")
    picked_by: Mapped[User | None] = relationship(foreign_keys=[picked_by_id], lazy="joined")
    packed_by: Mapped[User | None] = relationship(foreign_keys=[packed_by_id], lazy="joined")
    items: Mapped[list["DeliveryItem"]] = relationship(
        cascade="all, delete-orphan", order_by="DeliveryItem.id", lazy="selectin"
    )


class DeliveryItem(Base):
    __tablename__ = "delivery_items"
    __table_args__ = (
        UniqueConstraint("delivery_id", "product_id", name="uq_delivery_items_delivery_id_product_id"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    delivery_id: Mapped[int] = mapped_column(ForeignKey("deliveries.id", ondelete="CASCADE"), index=True, nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(QUANTITY_TYPE, nullable=False)

    product: Mapped[Product] = relationship(lazy="joined")

    # Filled for display on the detail endpoint (on-hand at the source); not stored.
    available_quantity = None

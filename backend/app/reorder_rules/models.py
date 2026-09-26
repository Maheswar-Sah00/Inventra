from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.locations.models import Location
from app.products.models import QUANTITY_TYPE, Product


class ReorderRule(TimestampMixin, Base):
    """Replenishment thresholds for one product at one location.

    Stock at the location <= minimum_quantity means the product needs reordering; target_quantity is the
    level to replenish up to. Evaluating stock against the rule is done by the inventory/dashboard modules.
    """

    __tablename__ = "reorder_rules"
    __table_args__ = (
        UniqueConstraint("product_id", "location_id", name="uq_reorder_rules_product_id_location_id"),
        CheckConstraint("minimum_quantity >= 0", name="minimum_quantity_non_negative"),
        CheckConstraint("target_quantity >= minimum_quantity", name="target_not_below_minimum"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Rules are configuration owned by the product/location, so they go with them if those are deleted.
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), index=True, nullable=False)
    minimum_quantity: Mapped[Decimal] = mapped_column(QUANTITY_TYPE, nullable=False)
    target_quantity: Mapped[Decimal] = mapped_column(QUANTITY_TYPE, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    product: Mapped[Product] = relationship(lazy="joined")
    location: Mapped[Location] = relationship(lazy="joined")

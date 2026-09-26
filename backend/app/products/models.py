from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.categories.models import Category
from app.core.database import Base, TimestampMixin
from app.locations.models import Location
from app.units.models import UnitOfMeasure

# Shared precision for quantities: up to 11 integer digits and 3 decimals (e.g. 12.5 kg).
QUANTITY_TYPE = Numeric(14, 3)


class Product(TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (CheckConstraint("initial_stock >= 0", name="initial_stock_non_negative"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), index=True, nullable=False)
    unit_of_measure_id: Mapped[int] = mapped_column(
        ForeignKey("units_of_measure.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    # What was entered when the product was created. This is a historical record, not a live stock
    # counter: current quantities belong to the inventory module (see app/products/events.py).
    initial_stock: Mapped[Decimal] = mapped_column(QUANTITY_TYPE, default=Decimal("0"), nullable=False)
    initial_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    category: Mapped[Category] = relationship(lazy="joined")
    unit_of_measure: Mapped[UnitOfMeasure] = relationship(lazy="joined")
    initial_location: Mapped[Location | None] = relationship(lazy="joined")

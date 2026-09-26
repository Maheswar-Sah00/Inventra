from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.warehouses.models import Warehouse


class Location(TimestampMixin, Base):
    """A place inside exactly one warehouse (rack, shelf, zone...). Stock moves between locations."""

    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "code", name="uq_locations_warehouse_id_code"),
        UniqueConstraint("warehouse_id", "name", name="uq_locations_warehouse_id_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # RESTRICT: a warehouse cannot be deleted while it still has locations.
    warehouse_id: Mapped[int] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    warehouse: Mapped[Warehouse] = relationship(lazy="joined")

    @property
    def is_usable(self) -> bool:
        """True when both the location and its warehouse are active."""
        return self.is_active and self.warehouse.is_active

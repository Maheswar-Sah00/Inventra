from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.categories.schemas import CategoryRef
from app.core.schemas import ORMModel, PatchModel
from app.core.types import Name, Quantity, Sku, UTCDatetime
from app.locations.schemas import LocationRef
from app.units.schemas import UnitRef


class ProductCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    sku: Sku
    category_id: int = Field(gt=0)
    unit_of_measure_id: int = Field(gt=0)
    initial_stock: Quantity = Decimal("0")
    # Where the initial stock is placed. Required when initial_stock > 0.
    initial_location_id: int | None = Field(default=None, gt=0)
    is_active: bool = True


class ProductUpdate(PatchModel):
    """initial_stock is fixed at creation; later quantity changes go through inventory operations."""

    name: Name | None = None
    sku: Sku | None = None
    category_id: int | None = Field(default=None, gt=0)
    unit_of_measure_id: int | None = Field(default=None, gt=0)
    is_active: bool | None = None


class ProductRef(ORMModel):
    id: int
    name: str
    sku: str
    is_active: bool


class ProductOut(ORMModel):
    id: int
    name: str
    sku: str
    category_id: int
    category: CategoryRef
    unit_of_measure_id: int
    unit_of_measure: UnitRef
    initial_stock: Quantity
    initial_location_id: int | None
    initial_location: LocationRef | None
    is_active: bool
    created_at: UTCDatetime
    updated_at: UTCDatetime

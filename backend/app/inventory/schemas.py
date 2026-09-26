from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PlainSerializer, field_validator

from app.categories.schemas import CategoryRef
from app.core.schemas import ORMModel
from app.core.types import Quantity, UTCDatetime
from app.inventory.documents import DocumentStatus
from app.inventory.models import MovementType
from app.locations.schemas import LocationRef
from app.units.schemas import UnitRef

# Strictly positive quantity for document lines.
PositiveQuantity = Annotated[Quantity, Field(gt=0)]

# Signed quantity (movements, adjustment differences), returned as a JSON number.
SignedQuantity = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]


def _blank_to_none(value: object) -> object:
    if isinstance(value, str):
        value = " ".join(value.split())
        return value or None
    return value


# Optional single-line text up to 100 characters (supplier/customer names and references).
OptionalShortText = Annotated[Annotated[str, Field(max_length=100)] | None, BeforeValidator(_blank_to_none)]

MAX_LINES = 200


class UserRef(ORMModel):
    id: int
    name: str


class InventoryProductRef(ORMModel):
    id: int
    name: str
    sku: str
    is_active: bool
    unit_of_measure: UnitRef


class StockProductRef(InventoryProductRef):
    category: CategoryRef


# --- Document lines -----------------------------------------------------------------------------


class LineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int = Field(gt=0)
    quantity: PositiveQuantity


def unique_products(lines: list) -> list:
    seen: set[int] = set()
    for line in lines:
        if line.product_id in seen:
            raise ValueError("Each product can appear only once per document; combine the quantities")
        seen.add(line.product_id)
    return lines


Lines = Annotated[list[LineIn], Field(min_length=1, max_length=MAX_LINES)]


class LinesMixin(BaseModel):
    @field_validator("items", check_fields=False)
    @classmethod
    def _unique_products(cls, items):
        return unique_products(items) if items is not None else items


class LineOut(ORMModel):
    id: int
    product_id: int
    product: InventoryProductRef
    quantity: Quantity


class OutgoingLineOut(LineOut):
    # On-hand stock at the source location; filled on the detail endpoint while the document is open.
    available_quantity: Quantity | None = None


# --- Documents ----------------------------------------------------------------------------------


class DocumentOut(ORMModel):
    id: int
    reference: str
    status: DocumentStatus
    scheduled_date: date | None
    notes: str | None
    created_by: UserRef
    validated_by: UserRef | None
    validated_at: UTCDatetime | None
    canceled_at: UTCDatetime | None
    created_at: UTCDatetime
    updated_at: UTCDatetime


# --- Stock & movements --------------------------------------------------------------------------


class StockOut(ORMModel):
    id: int
    product_id: int
    product: StockProductRef
    location_id: int
    location: LocationRef
    quantity: Quantity
    updated_at: UTCDatetime


class LocationQuantity(BaseModel):
    location: LocationRef
    quantity: Quantity


class ProductStockOut(BaseModel):
    product: StockProductRef
    total_quantity: Quantity
    locations: list[LocationQuantity]


class MovementOut(ORMModel):
    id: int
    movement_type: MovementType
    product_id: int
    product: InventoryProductRef
    # Signed: + stock entering, - stock leaving; transfers record the moved amount as positive.
    quantity: SignedQuantity
    source_location_id: int | None
    source_location: LocationRef | None
    destination_location_id: int | None
    destination_location: LocationRef | None
    reference_type: str
    reference_id: int
    reference_number: str
    performed_by: UserRef
    created_at: UTCDatetime

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from app.core.schemas import ORMModel, PatchModel
from app.core.types import OptionalText, Quantity
from app.inventory.schemas import MAX_LINES, DocumentOut, InventoryProductRef, LinesMixin, SignedQuantity
from app.locations.schemas import LocationRef


def _collapse(value: object) -> object:
    return " ".join(value.split()) if isinstance(value, str) else value


Reason = Annotated[str, BeforeValidator(_collapse), Field(min_length=1, max_length=255)]


class AdjustmentLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int = Field(gt=0)
    counted_quantity: Quantity  # >= 0


AdjustmentLines = Annotated[list[AdjustmentLineIn], Field(min_length=1, max_length=MAX_LINES)]


class AdjustmentCreate(LinesMixin):
    model_config = ConfigDict(extra="forbid")

    location_id: int = Field(gt=0)
    reason: Reason
    notes: OptionalText = None
    items: AdjustmentLines


class AdjustmentUpdate(PatchModel, LinesMixin):
    NULLABLE = frozenset({"notes"})

    location_id: int | None = Field(default=None, gt=0)
    reason: Reason | None = None
    notes: OptionalText = None
    items: AdjustmentLines | None = None


class AdjustmentLineOut(ORMModel):
    id: int
    product_id: int
    product: InventoryProductRef
    counted_quantity: Quantity
    # Set when validated: stock before the adjustment and counted - recorded.
    recorded_quantity: Quantity | None
    difference: SignedQuantity | None
    # Current on-hand while the adjustment is open (detail endpoint only).
    current_quantity: Quantity | None = None


class AdjustmentOut(DocumentOut):
    location_id: int
    location: LocationRef
    reason: str
    items: list[AdjustmentLineOut]

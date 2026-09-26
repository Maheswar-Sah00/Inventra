from datetime import date

from pydantic import ConfigDict, Field

from app.core.schemas import PatchModel
from app.core.types import Name, OptionalText
from app.inventory.schemas import DocumentOut, LineOut, Lines, LinesMixin, OptionalShortText
from app.locations.schemas import LocationRef


class ReceiptCreate(LinesMixin):
    model_config = ConfigDict(extra="forbid")

    supplier_name: Name
    supplier_reference: OptionalShortText = None
    destination_location_id: int = Field(gt=0)
    scheduled_date: date | None = None
    notes: OptionalText = None
    items: Lines


class ReceiptUpdate(PatchModel, LinesMixin):
    NULLABLE = frozenset({"supplier_reference", "scheduled_date", "notes"})

    supplier_name: Name | None = None
    supplier_reference: OptionalShortText = None
    destination_location_id: int | None = Field(default=None, gt=0)
    scheduled_date: date | None = None
    notes: OptionalText = None
    items: Lines | None = None


class ReceiptOut(DocumentOut):
    supplier_name: str
    supplier_reference: str | None
    destination_location_id: int
    destination_location: LocationRef
    items: list[LineOut]

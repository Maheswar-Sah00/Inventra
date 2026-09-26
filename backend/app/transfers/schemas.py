from datetime import date

from pydantic import ConfigDict, Field, ValidationInfo, field_validator

from app.core.schemas import PatchModel
from app.core.types import OptionalText
from app.inventory.schemas import DocumentOut, Lines, LinesMixin, OutgoingLineOut
from app.locations.schemas import LocationRef

SAME_LOCATION = "Source and destination must be different locations"


class TransferCreate(LinesMixin):
    model_config = ConfigDict(extra="forbid")

    source_location_id: int = Field(gt=0)
    destination_location_id: int = Field(gt=0)
    scheduled_date: date | None = None
    notes: OptionalText = None
    items: Lines

    @field_validator("destination_location_id")
    @classmethod
    def _different_locations(cls, value: int, info: ValidationInfo) -> int:
        if value == info.data.get("source_location_id"):
            raise ValueError(SAME_LOCATION)
        return value


class TransferUpdate(PatchModel, LinesMixin):
    NULLABLE = frozenset({"scheduled_date", "notes"})

    source_location_id: int | None = Field(default=None, gt=0)
    destination_location_id: int | None = Field(default=None, gt=0)
    scheduled_date: date | None = None
    notes: OptionalText = None
    items: Lines | None = None


class TransferOut(DocumentOut):
    source_location_id: int
    source_location: LocationRef
    destination_location_id: int
    destination_location: LocationRef
    items: list[OutgoingLineOut]

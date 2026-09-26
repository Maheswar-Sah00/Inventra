from datetime import date

from pydantic import ConfigDict, Field

from app.core.schemas import PatchModel
from app.core.types import OptionalText, UTCDatetime
from app.inventory.schemas import DocumentOut, Lines, LinesMixin, OptionalShortText, OutgoingLineOut, UserRef
from app.locations.schemas import LocationRef


class DeliveryCreate(LinesMixin):
    model_config = ConfigDict(extra="forbid")

    customer_name: OptionalShortText = None
    source_location_id: int = Field(gt=0)
    scheduled_date: date | None = None
    notes: OptionalText = None
    items: Lines


class DeliveryUpdate(PatchModel, LinesMixin):
    NULLABLE = frozenset({"customer_name", "scheduled_date", "notes"})

    customer_name: OptionalShortText = None
    source_location_id: int | None = Field(default=None, gt=0)
    scheduled_date: date | None = None
    notes: OptionalText = None
    items: Lines | None = None


class DeliveryOut(DocumentOut):
    customer_name: str | None
    source_location_id: int
    source_location: LocationRef
    picked_at: UTCDatetime | None
    picked_by: UserRef | None
    packed_at: UTCDatetime | None
    packed_by: UserRef | None
    items: list[OutgoingLineOut]

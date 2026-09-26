from pydantic import BaseModel, ConfigDict, Field

from app.core.schemas import ORMModel, PatchModel
from app.core.types import Code, Name, UTCDatetime
from app.warehouses.schemas import WarehouseRef


class LocationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    warehouse_id: int = Field(gt=0)
    name: Name
    code: Code
    is_active: bool = True


class LocationUpdate(PatchModel):
    """A location cannot move to another warehouse: stock history recorded against it would become wrong."""

    name: Name | None = None
    code: Code | None = None
    is_active: bool | None = None


class LocationRef(ORMModel):
    id: int
    name: str
    code: str
    is_active: bool
    warehouse: WarehouseRef


class LocationOut(ORMModel):
    id: int
    warehouse_id: int
    warehouse: WarehouseRef
    name: str
    code: str
    is_active: bool
    created_at: UTCDatetime
    updated_at: UTCDatetime

from pydantic import BaseModel, ConfigDict

from app.core.schemas import ORMModel, PatchModel
from app.core.types import Code, Name, OptionalText, UTCDatetime


class WarehouseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    code: Code
    address: OptionalText = None
    is_active: bool = True


class WarehouseUpdate(PatchModel):
    NULLABLE = frozenset({"address"})

    name: Name | None = None
    code: Code | None = None
    address: OptionalText = None
    is_active: bool | None = None


class WarehouseRef(ORMModel):
    id: int
    name: str
    code: str
    is_active: bool


class WarehouseOut(ORMModel):
    id: int
    name: str
    code: str
    address: str | None
    is_active: bool
    created_at: UTCDatetime
    updated_at: UTCDatetime

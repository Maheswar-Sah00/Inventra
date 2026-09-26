from pydantic import BaseModel, ConfigDict

from app.core.schemas import ORMModel, PatchModel
from app.core.types import Name, OptionalText, UTCDatetime


class CategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    description: OptionalText = None
    is_active: bool = True


class CategoryUpdate(PatchModel):
    NULLABLE = frozenset({"description"})

    name: Name | None = None
    description: OptionalText = None
    is_active: bool | None = None


class CategoryRef(ORMModel):
    id: int
    name: str


class CategoryOut(ORMModel):
    id: int
    name: str
    description: str | None
    is_active: bool
    created_at: UTCDatetime
    updated_at: UTCDatetime

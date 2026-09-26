from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.core.schemas import ORMModel, PatchModel
from app.core.types import Name, UTCDatetime

UnitName = Annotated[Name, Field(max_length=50)]
Symbol = Annotated[Name, Field(max_length=16)]


class UnitCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: UnitName
    symbol: Symbol
    is_active: bool = True


class UnitUpdate(PatchModel):
    name: UnitName | None = None
    symbol: Symbol | None = None
    is_active: bool | None = None


class UnitRef(ORMModel):
    id: int
    name: str
    symbol: str


class UnitOut(ORMModel):
    id: int
    name: str
    symbol: str
    is_active: bool
    created_at: UTCDatetime
    updated_at: UTCDatetime

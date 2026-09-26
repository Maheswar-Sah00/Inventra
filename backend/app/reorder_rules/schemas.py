from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from app.core.schemas import ORMModel, PatchModel
from app.core.types import Quantity, UTCDatetime
from app.locations.schemas import LocationRef
from app.products.schemas import ProductRef

TARGET_BELOW_MINIMUM = "Target quantity must be greater than or equal to the minimum quantity"


class ReorderRuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int = Field(gt=0)
    location_id: int = Field(gt=0)
    minimum_quantity: Quantity
    target_quantity: Quantity
    is_active: bool = True

    @field_validator("target_quantity")
    @classmethod
    def _target_not_below_minimum(cls, value, info: ValidationInfo):
        minimum = info.data.get("minimum_quantity")
        if minimum is not None and value < minimum:
            raise ValueError(TARGET_BELOW_MINIMUM)
        return value


class ReorderRuleUpdate(PatchModel):
    """Product and location are fixed; create a new rule to cover another pair."""

    minimum_quantity: Quantity | None = None
    target_quantity: Quantity | None = None
    is_active: bool | None = None


class ReorderRuleOut(ORMModel):
    id: int
    product_id: int
    product: ProductRef
    location_id: int
    location: LocationRef
    minimum_quantity: Quantity
    target_quantity: Quantity
    is_active: bool
    created_at: UTCDatetime
    updated_at: UTCDatetime

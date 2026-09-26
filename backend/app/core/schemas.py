"""Base Pydantic models shared by module schemas."""

from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, model_validator


class ORMModel(BaseModel):
    """Response model populated from ORM objects."""

    model_config = ConfigDict(from_attributes=True)


class PatchModel(BaseModel):
    """PATCH request body: only the fields sent are applied and unknown fields are rejected.

    Fields may be sent as null only if listed in NULLABLE (e.g. an optional description).
    """

    model_config = ConfigDict(extra="forbid")
    NULLABLE: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def _reject_nulls(self):
        invalid = sorted(f for f in self.model_fields_set if getattr(self, f) is None and f not in self.NULLABLE)
        if invalid:
            raise ValueError(f"{', '.join(invalid)} cannot be null")
        return self

    def changes(self) -> dict[str, Any]:
        return self.model_dump(exclude_unset=True)

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.database import as_utc
from app.users.models import UserRole


def clean_name(value: str) -> str:
    value = " ".join(value.split())
    if len(value) < 2:
        raise ValueError("Name must be at least 2 characters")
    return value


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    _utc = field_validator("created_at", "updated_at")(as_utc)


class UserUpdate(BaseModel):
    """Fields a user may change on their own profile. Role, email and status are deliberately absent."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)

    _clean_name = field_validator("name")(clean_name)

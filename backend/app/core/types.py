"""Reusable Pydantic field types shared across modules."""

import re
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, BeforeValidator, Field, PlainSerializer

from app.core.database import as_utc


def _collapse_whitespace(value: object) -> object:
    return " ".join(value.split()) if isinstance(value, str) else value


def _normalize_code(value: object) -> object:
    return value.strip().upper() if isinstance(value, str) else value


def _blank_to_none(value: object) -> object:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


# Timestamps read back from the database, always returned as timezone-aware UTC.
UTCDatetime = Annotated[datetime, AfterValidator(as_utc)]

# Required single-line text; surrounding/repeated whitespace is collapsed before validation.
Name = Annotated[str, BeforeValidator(_collapse_whitespace), Field(min_length=1, max_length=100)]

# Optional free text; blank becomes null.
OptionalText = Annotated[Annotated[str, Field(max_length=500)] | None, BeforeValidator(_blank_to_none)]

# Identifier codes (SKUs, warehouse/location codes): trimmed and upper-cased.
_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9._/-]*$")


def _check_code(value: str) -> str:
    if not _CODE_RE.match(value):
        raise ValueError("Use letters, numbers and . _ / - only, starting with a letter or number")
    return value


Code = Annotated[str, BeforeValidator(_normalize_code), Field(min_length=1, max_length=32), AfterValidator(_check_code)]
Sku = Annotated[str, BeforeValidator(_normalize_code), Field(min_length=1, max_length=64), AfterValidator(_check_code)]

# Non-negative stock quantity with up to 3 decimals (matches Numeric(14, 3) columns).
# Accepted as a JSON number or string; returned as a JSON number.
Quantity = Annotated[
    Decimal,
    Field(ge=0, max_digits=14, decimal_places=3),
    PlainSerializer(float, return_type=float, when_used="json"),
]

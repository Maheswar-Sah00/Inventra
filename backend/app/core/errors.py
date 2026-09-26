"""HTTP error helpers that keep FastAPI's error shape.

Field errors use the same `detail` list format as FastAPI's own validation errors, so the frontend
can show the message next to the offending field.
"""

from fastapi import HTTPException, status


def field_error(field: str, message: str, status_code: int = status.HTTP_422_UNPROCESSABLE_ENTITY) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=[{"loc": ["body", field], "msg": message, "type": "value_error"}],
    )


def conflict(field: str, message: str) -> HTTPException:
    """409 for a uniqueness violation on `field`."""
    return field_error(field, message, status.HTTP_409_CONFLICT)


def not_found(resource: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{resource} not found")


def in_use(resource: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"This {resource} is in use and cannot be deleted. Deactivate it instead.",
    )

"""Small persistence helpers shared by CRUD-style modules."""

from collections.abc import Iterable
from typing import Any, TypeVar

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import conflict, field_error, in_use, not_found

ModelT = TypeVar("ModelT")


def get_or_404(db: Session, model: type[ModelT], obj_id: int, resource: str) -> ModelT:
    obj = db.get(model, obj_id)
    if obj is None:
        raise not_found(resource)
    return obj


def get_reference(db: Session, model: type[ModelT], obj_id: int, *, field: str, label: str, require_active=True) -> ModelT:
    """Load an entity referenced by a request field, or raise a 422 pointing at that field."""
    obj = db.get(model, obj_id)
    if obj is None:
        raise field_error(field, f"{label} not found")
    if require_active and not getattr(obj, "is_active", True):
        raise field_error(field, f"{label} is inactive")
    return obj


def ensure_unique(
    db: Session,
    column,
    value: str,
    *,
    field: str,
    message: str,
    exclude_id: int | None = None,
    where: Iterable[Any] = (),
) -> None:
    """Raise 409 if another row has the same value in `column` (case-insensitive)."""
    model = column.class_
    statement = select(model.id).where(func.lower(column) == value.lower(), *where)
    if exclude_id is not None:
        statement = statement.where(model.id != exclude_id)
    if db.scalar(statement.limit(1)) is not None:
        raise conflict(field, message)


def apply_changes(obj: Any, changes: dict[str, Any]) -> None:
    for key, value in changes.items():
        setattr(obj, key, value)


def commit_or_conflict(db: Session, field: str, message: str) -> None:
    """Commit; a unique-constraint race that slipped past ensure_unique becomes a 409."""
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise conflict(field, message) from None


def delete_or_conflict(db: Session, obj: Any, resource: str) -> None:
    """Delete `obj`; if other rows still reference it (FK RESTRICT), return 409 instead."""
    db.delete(obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise in_use(resource) from None

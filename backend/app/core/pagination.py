"""Offset pagination shared by list endpoints.

Usage:
    @router.get("", response_model=Page[ThingOut])
    def list_things(page: PageParamsDep, db: DbSession):
        return paginate(db, select(Thing).order_by(Thing.name), page, ThingOut)
"""

from typing import Annotated, Generic, TypeVar

from fastapi import Depends, Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

T = TypeVar("T")

MAX_PAGE_SIZE = 500


class PageParams(BaseModel):
    limit: int
    offset: int


def page_params(
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE, description="Items per page")] = 50,
    offset: Annotated[int, Query(ge=0, description="Items to skip")] = 0,
) -> PageParams:
    return PageParams(limit=limit, offset=offset)


PageParamsDep = Annotated[PageParams, Depends(page_params)]


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


def paginate(db: Session, statement: Select, params: PageParams, schema: type[BaseModel]) -> Page:
    total = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery()))
    rows = db.scalars(statement.limit(params.limit).offset(params.offset)).unique().all()
    return Page(
        items=[schema.model_validate(row) for row in rows],
        total=total or 0,
        limit=params.limit,
        offset=params.offset,
    )


def contains(column, text: str):
    """Case-insensitive substring match with LIKE wildcards in `text` escaped."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return column.ilike(f"%{escaped}%", escape="\\")

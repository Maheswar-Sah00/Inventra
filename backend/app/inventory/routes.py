from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.database import get_db
from app.core.pagination import Page, PageParamsDep
from app.inventory import queries
from app.inventory.models import MovementType
from app.inventory.schemas import MovementOut, ProductStockOut, StockOut

# Read-only. Stock changes only through receipts, deliveries, transfers and adjustments.
router = APIRouter(tags=["stock"], dependencies=[Depends(get_current_user)])
DbSession = Annotated[Session, Depends(get_db)]
Search = Annotated[str | None, Query(max_length=100, description="Product name or SKU")]


@router.get("/stock", response_model=Page[StockOut])
def list_stock(
    db: DbSession,
    page: PageParamsDep,
    product_id: int | None = None,
    location_id: int | None = None,
    warehouse_id: int | None = None,
    category_id: int | None = None,
    q: Search = None,
    include_empty: Annotated[bool, Query(description="Include positions with zero quantity")] = False,
):
    """Current on-hand quantity per product and location."""
    return queries.list_stock(
        db,
        page,
        product_id=product_id,
        location_id=location_id,
        warehouse_id=warehouse_id,
        category_id=category_id,
        q=q,
        include_empty=include_empty,
    )


@router.get("/stock/products/{product_id}", response_model=ProductStockOut)
def product_stock(product_id: int, db: DbSession, warehouse_id: int | None = None):
    """Total on-hand quantity of one product and its breakdown by location."""
    return queries.product_stock(db, product_id, warehouse_id)


@router.get("/stock-movements", response_model=Page[MovementOut])
def list_movements(
    db: DbSession,
    page: PageParamsDep,
    product_id: int | None = None,
    location_id: int | None = None,
    warehouse_id: int | None = None,
    category_id: int | None = None,
    movement_type: Annotated[list[MovementType] | None, Query(description="Repeat to match several")] = None,
    reference_type: str | None = None,
    reference_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    q: Annotated[str | None, Query(max_length=100, description="Product name/SKU or document reference")] = None,
):
    """Stock ledger: every stock change, newest first."""
    return queries.list_movements(
        db,
        page,
        product_id=product_id,
        location_id=location_id,
        warehouse_id=warehouse_id,
        category_id=category_id,
        movement_types=movement_type,
        reference_type=reference_type,
        reference_id=reference_id,
        date_from=date_from,
        date_to=date_to,
        q=q,
    )

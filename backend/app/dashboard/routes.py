from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.database import get_db
from app.core.pagination import Page, PageParamsDep
from app.dashboard import services
from app.dashboard.schemas import AppliedFilters, AvailabilityRow, DashboardSummary, DocumentType, StockStatus
from app.inventory.documents import DocumentStatus

# Read-only visibility endpoints for every signed-in user (both roles).
router = APIRouter(tags=["dashboard"], dependencies=[Depends(get_current_user)])
DbSession = Annotated[Session, Depends(get_db)]


def scope_filters(
    document_type: DocumentType | None = None,
    status: DocumentStatus | None = None,
    warehouse_id: Annotated[int | None, Query(gt=0)] = None,
    location_id: Annotated[int | None, Query(gt=0)] = None,
    category_id: Annotated[int | None, Query(gt=0)] = None,
) -> AppliedFilters:
    return AppliedFilters(
        document_type=document_type,
        status=status,
        warehouse_id=warehouse_id,
        location_id=location_id,
        category_id=category_id,
    )


Filters = Annotated[AppliedFilters, Depends(scope_filters)]


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(filters: Filters, db: DbSession):
    """KPIs and document counts, aggregated in the database.

    warehouse_id / location_id / category_id narrow both stock and document figures.
    document_type limits the operation figures to one type (others are null).
    status replaces the default "pending" statuses (DRAFT, WAITING, READY) for the operation figures.
    """
    return services.summary(db, filters)


@router.get("/stock-availability", response_model=Page[AvailabilityRow])
def stock_availability(
    db: DbSession,
    page: PageParamsDep,
    warehouse_id: Annotated[int | None, Query(gt=0)] = None,
    location_id: Annotated[int | None, Query(gt=0)] = None,
    category_id: Annotated[int | None, Query(gt=0)] = None,
    product_id: Annotated[int | None, Query(gt=0)] = None,
    stock_status: Annotated[list[StockStatus] | None, Query(alias="status", description="Repeatable")] = None,
    q: Annotated[str | None, Query(max_length=100, description="Product name or SKU")] = None,
):
    """Per product/location stock with IN_STOCK / LOW_STOCK / OUT_OF_STOCK, most urgent first."""
    filters = AppliedFilters(warehouse_id=warehouse_id, location_id=location_id, category_id=category_id)
    return services.list_availability(db, page, filters, statuses=stock_status, product_id=product_id, q=q)

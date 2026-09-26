import enum

from pydantic import BaseModel

from app.categories.schemas import CategoryRef
from app.core.types import Quantity
from app.inventory.documents import DocumentStatus
from app.inventory.schemas import InventoryProductRef
from app.locations.schemas import LocationRef


class StockStatus(str, enum.Enum):
    IN_STOCK = "IN_STOCK"
    LOW_STOCK = "LOW_STOCK"  # 0 < on hand <= reorder rule minimum
    OUT_OF_STOCK = "OUT_OF_STOCK"  # on hand == 0


class DocumentType(str, enum.Enum):
    """Matches stock_movements.reference_type for the four operations."""

    RECEIPT = "RECEIPT"
    DELIVERY = "DELIVERY"
    TRANSFER = "TRANSFER"
    ADJUSTMENT = "ADJUSTMENT"


class AppliedFilters(BaseModel):
    document_type: DocumentType | None = None
    status: DocumentStatus | None = None
    warehouse_id: int | None = None
    location_id: int | None = None
    category_id: int | None = None


class DocumentTypeCounts(BaseModel):
    document_type: DocumentType
    # Number of documents per status (only the filtered status when a status filter is set).
    counts: dict[DocumentStatus, int]
    total: int


class DashboardSummary(BaseModel):
    # Inventory KPIs (stock-based; not affected by document_type/status filters).
    total_products_in_stock: int
    low_stock_items: int
    out_of_stock_items: int
    # Operation KPIs: documents whose status is in `counted_statuses`. null when excluded by document_type.
    pending_receipts: int | None
    pending_deliveries: int | None
    scheduled_transfers: int | None
    counted_statuses: list[DocumentStatus]
    documents: list[DocumentTypeCounts]
    filters: AppliedFilters


class AvailabilityRow(BaseModel):
    product: InventoryProductRef
    category: CategoryRef
    location: LocationRef
    quantity: Quantity
    # From the active reorder rule for this product/location, if any.
    minimum_quantity: Quantity | None
    target_quantity: Quantity | None
    status: StockStatus

import type { DocumentStatus, InventoryProductRef } from "../inventory/types";
import type { CategoryRef, LocationRef } from "../master-data/types";

export type StockStatus = "IN_STOCK" | "LOW_STOCK" | "OUT_OF_STOCK";
export type DocumentType = "RECEIPT" | "DELIVERY" | "TRANSFER" | "ADJUSTMENT";

export const DOCUMENT_TYPES: { value: DocumentType; label: string; path: string }[] = [
  { value: "RECEIPT", label: "Receipts", path: "/receipts" },
  { value: "DELIVERY", label: "Deliveries", path: "/deliveries" },
  { value: "TRANSFER", label: "Internal Transfers", path: "/transfers" },
  { value: "ADJUSTMENT", label: "Adjustments", path: "/adjustments" },
];

export type DashboardSummary = {
  total_products_in_stock: number;
  low_stock_items: number;
  out_of_stock_items: number;
  pending_receipts: number | null;
  pending_deliveries: number | null;
  scheduled_transfers: number | null;
  counted_statuses: DocumentStatus[];
  documents: { document_type: DocumentType; counts: Partial<Record<DocumentStatus, number>>; total: number }[];
};

export type AvailabilityRow = {
  product: InventoryProductRef;
  category: CategoryRef;
  location: LocationRef;
  quantity: number;
  minimum_quantity: number | null;
  target_quantity: number | null;
  status: StockStatus;
};

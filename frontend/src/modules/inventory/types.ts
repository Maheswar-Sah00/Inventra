import type { CategoryRef, LocationRef, UnitRef } from "../master-data/types";

export type DocumentStatus = "DRAFT" | "WAITING" | "READY" | "DONE" | "CANCELED";
export const OPEN_STATUSES: DocumentStatus[] = ["DRAFT", "WAITING", "READY"];

export type OperationKind = "receipts" | "deliveries" | "transfers" | "adjustments";
export type DocumentAction = "confirm" | "pick" | "pack" | "validate" | "cancel";

export type UserRef = { id: number; name: string };
export type InventoryProductRef = { id: number; name: string; sku: string; is_active: boolean; unit_of_measure: UnitRef };

/** A document line. Receipts/deliveries/transfers use `quantity`; adjustments use the count fields. */
export type DocumentLine = {
  id: number;
  product_id: number;
  product: InventoryProductRef;
  quantity?: number;
  available_quantity?: number | null;
  counted_quantity?: number;
  recorded_quantity?: number | null;
  difference?: number | null;
  current_quantity?: number | null;
};

export type InventoryDocument = {
  id: number;
  reference: string;
  status: DocumentStatus;
  scheduled_date: string | null;
  notes: string | null;
  created_by: UserRef;
  validated_by: UserRef | null;
  validated_at: string | null;
  canceled_at: string | null;
  created_at: string;
  updated_at: string;
  items: DocumentLine[];
  // Receipts
  supplier_name?: string;
  supplier_reference?: string | null;
  destination_location_id?: number;
  destination_location?: LocationRef;
  // Deliveries
  customer_name?: string | null;
  picked_at?: string | null;
  picked_by?: UserRef | null;
  packed_at?: string | null;
  packed_by?: UserRef | null;
  // Deliveries & transfers
  source_location_id?: number;
  source_location?: LocationRef;
  // Adjustments
  location_id?: number;
  location?: LocationRef;
  reason?: string;
};

export type StockPosition = {
  id: number;
  product_id: number;
  product: InventoryProductRef & { category: CategoryRef };
  location_id: number;
  location: LocationRef;
  quantity: number;
  updated_at: string;
};

export type ProductStock = {
  product: InventoryProductRef & { category: CategoryRef };
  total_quantity: number;
  locations: { location: LocationRef; quantity: number }[];
};

export type MovementType = "INITIAL_STOCK" | "RECEIPT" | "DELIVERY" | "TRANSFER" | "ADJUSTMENT";

export type StockMovement = {
  id: number;
  movement_type: MovementType;
  product_id: number;
  product: InventoryProductRef;
  quantity: number;
  source_location_id: number | null;
  source_location: LocationRef | null;
  destination_location_id: number | null;
  destination_location: LocationRef | null;
  reference_type: string;
  reference_id: number;
  reference_number: string;
  performed_by: UserRef;
  created_at: string;
};

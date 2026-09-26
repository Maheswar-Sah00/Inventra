import { locationLabel } from "../master-data/types";
import type { InventoryDocument, OperationKind } from "./types";

export type HeaderField =
  | { name: string; label: string; type: "text"; required?: boolean; maxLength?: number; hint?: string }
  | { name: string; label: string; type: "location"; hint?: string }
  | { name: string; label: string; type: "date" };

export type OperationConfig = {
  kind: OperationKind;
  title: string;
  singular: string;
  description: string;
  /** Value of stock_movements.reference_type for this document type. */
  movementReference: string;
  headerFields: HeaderField[];
  /** Line quantity field sent to the API. */
  quantityField: "quantity" | "counted_quantity";
  quantityLabel: string;
  /** Header field whose location's stock is shown next to each line. */
  stockLocationField?: "source_location_id" | "location_id";
  /** Deliveries go through pick and pack before validation. */
  pickPack?: boolean;
  confirmLabel: string;
  /** Short "who/where" text for lists. */
  summary: (doc: InventoryDocument) => string;
};

const notes: HeaderField = { name: "notes", label: "Notes", type: "text", maxLength: 500 };
const scheduled: HeaderField = { name: "scheduled_date", label: "Scheduled date", type: "date" };

export const OPERATIONS: Record<OperationKind, OperationConfig> = {
  receipts: {
    kind: "receipts",
    title: "Receipts",
    singular: "receipt",
    description: "Incoming goods from suppliers. Validating a receipt adds the stock.",
    movementReference: "RECEIPT",
    headerFields: [
      { name: "supplier_name", label: "Supplier", type: "text", required: true, maxLength: 100 },
      { name: "supplier_reference", label: "Supplier reference", type: "text", maxLength: 100, hint: "e.g. invoice or PO number" },
      { name: "destination_location_id", label: "Receive into", type: "location" },
      scheduled,
      notes,
    ],
    quantityField: "quantity",
    quantityLabel: "Quantity",
    confirmLabel: "Mark as ready",
    summary: (d) => `${d.supplier_name} → ${d.destination_location ? locationLabel(d.destination_location) : ""}`,
  },
  deliveries: {
    kind: "deliveries",
    title: "Delivery Orders",
    singular: "delivery order",
    description: "Outgoing goods. Confirm, pick, pack, then validate to remove the stock.",
    movementReference: "DELIVERY",
    headerFields: [
      { name: "customer_name", label: "Customer", type: "text", maxLength: 100 },
      { name: "source_location_id", label: "Ship from", type: "location" },
      scheduled,
      notes,
    ],
    quantityField: "quantity",
    quantityLabel: "Quantity",
    stockLocationField: "source_location_id",
    pickPack: true,
    confirmLabel: "Check availability",
    summary: (d) => `${d.source_location ? locationLabel(d.source_location) : ""} → ${d.customer_name ?? "Customer"}`,
  },
  transfers: {
    kind: "transfers",
    title: "Internal Transfers",
    singular: "transfer",
    description: "Move stock between locations or warehouses. Total stock is unchanged.",
    movementReference: "TRANSFER",
    headerFields: [
      { name: "source_location_id", label: "From", type: "location" },
      { name: "destination_location_id", label: "To", type: "location" },
      scheduled,
      notes,
    ],
    quantityField: "quantity",
    quantityLabel: "Quantity",
    stockLocationField: "source_location_id",
    confirmLabel: "Check availability",
    summary: (d) =>
      `${d.source_location ? locationLabel(d.source_location) : ""} → ${d.destination_location ? locationLabel(d.destination_location) : ""}`,
  },
  adjustments: {
    kind: "adjustments",
    title: "Inventory Adjustments",
    singular: "adjustment",
    description: "Record a physical count. Validating sets stock to the counted quantities.",
    movementReference: "ADJUSTMENT",
    headerFields: [
      { name: "location_id", label: "Location", type: "location" },
      { name: "reason", label: "Reason", type: "text", required: true, maxLength: 255, hint: "e.g. Cycle count, Damaged goods" },
      notes,
    ],
    quantityField: "counted_quantity",
    quantityLabel: "Counted quantity",
    stockLocationField: "location_id",
    confirmLabel: "Mark as ready",
    summary: (d) => `${d.location ? locationLabel(d.location) : ""} · ${d.reason ?? ""}`,
  },
};

export const STATUS_LABELS: Record<string, string> = {
  DRAFT: "Draft",
  WAITING: "Waiting",
  READY: "Ready",
  DONE: "Done",
  CANCELED: "Canceled",
};

export function formatQuantity(value: number | null | undefined, unit?: string): string {
  if (value === null || value === undefined) return "—";
  const text = Number(value).toLocaleString(undefined, { maximumFractionDigits: 3 });
  return unit ? `${text} ${unit}` : text;
}

export function formatDateTime(value: string | null | undefined): string {
  return value ? new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—";
}

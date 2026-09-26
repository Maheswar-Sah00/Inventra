import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { SelectField } from "../../components/ui/FormField";
import { formatDateTime, formatQuantity } from "../inventory/operations";
import type { StockMovement } from "../inventory/types";
import { ALL, categoriesApi, locationsApi, warehousesApi } from "../master-data/api";
import { locationLabel, type Category, type Location, type Warehouse } from "../master-data/types";
import type { StockStatus } from "./types";

const STOCK_STATUS_LABELS: Record<StockStatus, string> = {
  IN_STOCK: "In stock",
  LOW_STOCK: "Low stock",
  OUT_OF_STOCK: "Out of stock",
};

/** Status is always spelled out, never shown by colour alone. */
export function StockStatusBadge({ status }: { status: StockStatus }) {
  return <span className={`badge stock-${status.toLowerCase().replace(/_/g, "-")}`}>{STOCK_STATUS_LABELS[status]}</span>;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="alert alert-error error-state" role="alert">
      <span>{message}</span>
      {onRetry && (
        <button type="button" className="btn btn-secondary" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <p className="empty-state muted">{children}</p>;
}

export function KpiCard({
  label,
  value,
  detail,
  to,
  loading,
  disabledReason,
}: {
  label: string;
  value: ReactNode;
  detail?: ReactNode;
  to?: string;
  loading?: boolean;
  disabledReason?: string;
}) {
  const body = (
    <>
      <span className="kpi-label">{label}</span>
      {loading ? (
        <span className="kpi-value kpi-loading" aria-live="polite">
          Loading…
        </span>
      ) : disabledReason ? (
        <span className="kpi-value kpi-muted">—</span>
      ) : (
        <span className="kpi-value">{value}</span>
      )}
      <span className="kpi-detail">{disabledReason ?? detail}</span>
    </>
  );
  return to && !loading && !disabledReason ? (
    <Link to={to} className="kpi-card kpi-link">
      {body}
    </Link>
  ) : (
    <div className="kpi-card">{body}</div>
  );
}

type Options = { warehouses: Warehouse[]; locations: Location[]; categories: Category[] };

/** Warehouses, locations and categories for filter dropdowns, loaded from the master-data APIs. */
export function useFilterOptions(): Options & { error: boolean } {
  const [options, setOptions] = useState<Options>({ warehouses: [], locations: [], categories: [] });
  const [error, setError] = useState(false);
  useEffect(() => {
    Promise.all([
      warehousesApi.list({ limit: ALL }),
      locationsApi.list({ limit: ALL }),
      categoriesApi.list({ limit: ALL }),
    ])
      .then(([warehouses, locations, categories]) =>
        setOptions({ warehouses: warehouses.items, locations: locations.items, categories: categories.items }),
      )
      .catch(() => setError(true));
  }, []);
  return { ...options, error };
}

/** Warehouse, location (narrowed to the warehouse) and category selects. */
export function ScopeFilters({
  options,
  values,
  onChange,
}: {
  options: Options;
  values: { warehouse_id: string; location_id: string; category_id: string };
  onChange: (changes: Partial<Record<"warehouse_id" | "location_id" | "category_id", string>>) => void;
}) {
  const locations = values.warehouse_id
    ? options.locations.filter((l) => String(l.warehouse_id) === values.warehouse_id)
    : options.locations;
  return (
    <>
      <SelectField
        label="Warehouse"
        value={values.warehouse_id}
        onChange={(e) => {
          const warehouseId = e.target.value;
          const location = options.locations.find((l) => String(l.id) === values.location_id);
          // Drop a location that is not in the newly chosen warehouse.
          const keepLocation = !warehouseId || !location || String(location.warehouse_id) === warehouseId;
          onChange({ warehouse_id: warehouseId, ...(keepLocation ? {} : { location_id: "" }) });
        }}
      >
        <option value="">All warehouses</option>
        {options.warehouses.map((w) => (
          <option key={w.id} value={w.id}>
            {w.name}
          </option>
        ))}
      </SelectField>
      <SelectField label="Location" value={values.location_id} onChange={(e) => onChange({ location_id: e.target.value })}>
        <option value="">All locations</option>
        {locations.map((l) => (
          <option key={l.id} value={l.id}>
            {locationLabel(l)}
          </option>
        ))}
      </SelectField>
      <SelectField label="Category" value={values.category_id} onChange={(e) => onChange({ category_id: e.target.value })}>
        <option value="">All categories</option>
        {options.categories.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </SelectField>
    </>
  );
}

export const MOVEMENT_LABELS: Record<string, string> = {
  INITIAL_STOCK: "Initial stock",
  RECEIPT: "Receipt",
  DELIVERY: "Delivery",
  TRANSFER: "Transfer",
  ADJUSTMENT: "Adjustment",
};

const REFERENCE_PATHS: Record<string, string> = {
  RECEIPT: "/receipts",
  DELIVERY: "/deliveries",
  TRANSFER: "/transfers",
  ADJUSTMENT: "/adjustments",
  PRODUCT: "/products",
};

function signedQuantity(value: number, unit: string) {
  const text = formatQuantity(Math.abs(value), unit);
  return value > 0 ? `+${text}` : value < 0 ? `−${text}` : text;
}

/** Stock ledger rows (Ravi's stock_movements), newest first. */
export function MovementTable({ movements, compact = false }: { movements: StockMovement[]; compact?: boolean }) {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>Date / time</th>
            <th>Type</th>
            <th>Product</th>
            <th className="num">Quantity</th>
            <th>From</th>
            <th>To</th>
            <th>Reference</th>
            {!compact && <th>Performed by</th>}
          </tr>
        </thead>
        <tbody>
          {movements.map((m) => {
            const path = REFERENCE_PATHS[m.reference_type];
            return (
              <tr key={m.id}>
                <td className="small">{formatDateTime(m.created_at)}</td>
                <td>{MOVEMENT_LABELS[m.movement_type] ?? m.movement_type}</td>
                <td>
                  <Link to={`/products/${m.product_id}`}>{m.product.name}</Link>{" "}
                  <span className="muted mono small">{m.product.sku}</span>
                </td>
                <td className={`num ${m.quantity < 0 ? "text-danger" : ""}`}>
                  {signedQuantity(m.quantity, m.product.unit_of_measure.symbol)}
                </td>
                <td>{m.source_location ? locationLabel(m.source_location) : "—"}</td>
                <td>{m.destination_location ? locationLabel(m.destination_location) : "—"}</td>
                <td>
                  {path ? (
                    <Link to={`${path}/${m.reference_id}`} className="mono">
                      {m.reference_number}
                    </Link>
                  ) : (
                    <span className="mono">{m.reference_number}</span>
                  )}
                </td>
                {!compact && <td>{m.performed_by.name}</td>}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

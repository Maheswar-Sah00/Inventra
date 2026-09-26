import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { SelectField } from "../../components/ui/FormField";
import { Icon, type IconName } from "../../components/ui/Icon";
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
  icon,
  hero = false,
}: {
  label: string;
  value: ReactNode;
  detail?: ReactNode;
  to?: string;
  loading?: boolean;
  disabledReason?: string;
  icon?: IconName;
  /** The dark lead card of the KPI row. */
  hero?: boolean;
}) {
  const linked = Boolean(to && !loading && !disabledReason);
  const body = (
    <>
      <span className="kpi-top">
        <span className="kpi-label">{label}</span>
        {(linked || icon) && (
          <span className="kpi-icon">
            <Icon name={linked ? "arrowUpRight" : icon!} size={16} />
          </span>
        )}
      </span>
      {loading ? (
        <span className="kpi-value kpi-loading" aria-live="polite">
          Loading…
        </span>
      ) : disabledReason ? (
        <span className="kpi-value kpi-muted">—</span>
      ) : (
        <span className="kpi-value">{value}</span>
      )}
      <span className="kpi-detail">
        {icon && !disabledReason && <Icon name={icon} size={14} />}
        {disabledReason ?? detail}
      </span>
    </>
  );
  const className = `kpi-card${hero ? " kpi-hero surface-dark" : ""}`;
  return linked ? (
    <Link to={to!} className={`${className} kpi-link`}>
      {body}
    </Link>
  ) : (
    <div className={className}>{body}</div>
  );
}

/** Two-letter tile standing in for a product image. */
export function Thumb({ name }: { name: string }) {
  const letters = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase();
  return (
    <span className="thumb" aria-hidden="true">
      {letters || "?"}
    </span>
  );
}

/** Rounds `max` up to 4 even steps of 1, 2, 2.5 or 5 x 10^n so the axis reads cleanly. */
function niceScale(max: number) {
  if (max <= 4) return { top: 4, step: 1 };
  const raw = max / 4;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((candidate) => candidate >= raw)!;
  return { top: step * 4, step };
}

export type ChartColumn = {
  label: string;
  /** Stacked from the bottom up; each segment key has a legend entry. */
  segments: { key: string; value: number }[];
  highlighted?: boolean;
};

/**
 * Stacked bar chart. Decorative: the same numbers are always shown in a table next to it,
 * so it is hidden from assistive tech.
 */
export function BarChart({ columns, legend }: { columns: ChartColumn[]; legend: { key: string; label: string }[] }) {
  const totals = columns.map((c) => c.segments.reduce((sum, segment) => sum + segment.value, 0));
  const { top, step } = niceScale(Math.max(0, ...totals));
  const ticks = [0, 1, 2, 3, 4].map((i) => i * step);
  const columnsTemplate = { gridTemplateColumns: `repeat(${columns.length}, minmax(0, 1fr))` };
  return (
    <div className="chart" aria-hidden="true">
      <div className="chart-body">
        <div className="chart-axis">
          {ticks.map((tick) => (
            <span key={tick} style={{ bottom: `${(tick / top) * 100}%` }}>
              {Number.isInteger(tick) ? tick : tick.toFixed(1)}
            </span>
          ))}
        </div>
        <div className="chart-plot" style={columnsTemplate}>
          {ticks.map((tick) => (
            <span key={tick} className="chart-gridline" style={{ bottom: `${(tick / top) * 100}%` }} />
          ))}
          {columns.map((column, index) => (
            <div key={column.label} className={`chart-col${column.highlighted ? " highlighted" : ""}`}>
              <div
                className={`chart-bar${totals[index] === 0 ? " empty" : ""}`}
                style={totals[index] ? { height: `${(totals[index] / top) * 100}%` } : undefined}
                title={`${column.label}: ${totals[index]}`}
              >
                {column.segments
                  .filter((segment) => segment.value > 0)
                  .map((segment) => (
                    <span key={segment.key} className={`chart-seg seg-${segment.key}`} style={{ flexGrow: segment.value }} />
                  ))}
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="chart-labels" style={columnsTemplate}>
        {columns.map((column) => (
          <span key={column.label} className={column.highlighted ? "highlighted" : undefined}>
            {column.label}
          </span>
        ))}
      </div>
      <div className="chart-legend">
        {legend.map((item) => (
          <span key={item.key}>
            <i className={`seg-${item.key}`} />
            {item.label}
          </span>
        ))}
      </div>
    </div>
  );
}

/** Ring showing a percentage, with the number printed in the middle. */
export function Donut({ percent, label }: { percent: number | null; label: string }) {
  const value = percent === null ? 0 : Math.max(0, Math.min(100, percent));
  return (
    <span className="donut" role="img" aria-label={percent === null ? `${label}: no data` : `${label}: ${Math.round(value)}%`}>
      <svg viewBox="0 0 36 36" width="76" height="76">
        <circle className="donut-track" cx="18" cy="18" r="15.915" />
        {value > 0 && (
          <circle className="donut-value" cx="18" cy="18" r="15.915" strokeDasharray={`${value} ${100 - value}`} strokeDashoffset="25" />
        )}
      </svg>
      <span className="donut-label" aria-hidden="true">
        {percent === null ? "—" : `${Math.round(value)}%`}
      </span>
    </span>
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
    <div className={compact ? "table-wrap flush" : "table-wrap"}>
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
                <td className="small muted nowrap">{formatDateTime(m.created_at)}</td>
                <td>
                  <span className={`type-pill type-${m.movement_type.toLowerCase().replace(/_/g, "-")}`}>
                    {MOVEMENT_LABELS[m.movement_type] ?? m.movement_type}
                  </span>
                </td>
                <td>
                  <span className="product-cell">
                    <Thumb name={m.product.name} />
                    <span className="product-cell-text">
                      <Link to={`/products/${m.product_id}`}>{m.product.name}</Link>
                      <span className="muted mono small">{m.product.sku}</span>
                    </span>
                  </span>
                </td>
                <td className={`num qty ${m.quantity < 0 ? "qty-out" : m.quantity > 0 ? "qty-in" : ""}`}>
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

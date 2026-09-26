import { Link } from "react-router-dom";

import { Button } from "../../components/ui/Button";
import { SelectField } from "../../components/ui/FormField";
import { Icon } from "../../components/ui/Icon";
import { PageHeader } from "../../components/ui/PageHeader";
import { useAuth } from "../../modules/auth";
import { dashboardApi } from "../../modules/dashboard/api";
import {
  BarChart,
  Donut,
  EmptyState,
  ErrorState,
  KpiCard,
  MovementTable,
  ScopeFilters,
  StockStatusBadge,
  Thumb,
  useFilterOptions,
} from "../../modules/dashboard/components";
import { useApiData, useUrlFilters } from "../../modules/dashboard/hooks";
import { DOCUMENT_TYPES, type DashboardSummary, type DocumentType } from "../../modules/dashboard/types";
import { stockApi } from "../../modules/inventory/api";
import { formatQuantity, STATUS_LABELS } from "../../modules/inventory/operations";
import type { DocumentStatus } from "../../modules/inventory/types";
import { locationLabel } from "../../modules/master-data/types";

const FILTER_KEYS = ["document_type", "status", "warehouse_id", "location_id", "category_id"] as const;
const ALL_STATUSES = Object.keys(STATUS_LABELS) as DocumentStatus[];
const OPEN: DocumentStatus[] = ["DRAFT", "WAITING", "READY"];
const CHART_LEGEND = [
  { key: "done", label: "Done" },
  { key: "open", label: "Open (draft, waiting, ready)" },
  { key: "canceled", label: "Canceled" },
];

function query(params: Record<string, string | undefined>) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => value && search.set(key, value));
  const text = search.toString();
  return text ? `?${text}` : "";
}

const shortLabel = (label: string) => label.replace("Internal ", "");

/** Done documents as a share of all documents that were not canceled; null when there are none. */
function completion(documents: DashboardSummary["documents"]) {
  let done = 0;
  let countable = 0;
  for (const doc of documents) {
    done += doc.counts.DONE ?? 0;
    countable += doc.total - (doc.counts.CANCELED ?? 0);
  }
  return { done, countable, percent: countable ? (done / countable) * 100 : null };
}

export function DashboardPage() {
  const { user } = useAuth();
  const filters = useUrlFilters(FILTER_KEYS);
  const f = filters.values;
  const options = useFilterOptions();
  const scope = { warehouse_id: f.warehouse_id, location_id: f.location_id, category_id: f.category_id };

  const summary = useApiData((params, signal) => dashboardApi.summary(params, signal), { ...f });
  const alerts = useApiData(
    (params, signal) => dashboardApi.availability({ ...params, status: ["OUT_OF_STOCK", "LOW_STOCK"], limit: 6 }, signal),
    scope,
  );
  const activity = useApiData(
    (params, signal) => stockApi.movements({ ...params, limit: 8 }, signal),
    { ...scope, movement_type: f.document_type },
  );

  const s = summary.data;
  const statusLabel = f.status ? STATUS_LABELS[f.status] : null;
  const excluded = (type: DocumentType) => (f.document_type && f.document_type !== type ? "Hidden by the document type filter" : undefined);
  const operationLink = (path: string) => `${path}${query({ status: f.status, warehouse_id: f.warehouse_id })}`;
  const stockLink = (statuses: string) => `/stock-availability${query({ ...scope, status: statuses })}`;
  const refresh = () => {
    summary.retry();
    alerts.retry();
    activity.retry();
  };
  const progress = s && !f.status ? completion(s.documents) : null;

  return (
    <section className="page page-wide dashboard">
      <PageHeader
        title="Inventory Dashboard"
        description={`Welcome${user ? `, ${user.name}` : ""}. Here is what is happening with inventory right now.`}
        actions={
          <Button type="button" variant="secondary" onClick={refresh}>
            <Icon name="rotate" size={16} />
            Refresh
          </Button>
        }
      />

      <form className="dashboard-filters" aria-label="Dashboard filters" onSubmit={(e) => e.preventDefault()}>
        <div className="segmented" role="group" aria-label="Document type">
          {[{ value: "", label: "All" }, ...DOCUMENT_TYPES].map((type) => (
            <button
              key={type.value}
              type="button"
              aria-pressed={f.document_type === type.value}
              onClick={() => filters.update({ document_type: type.value })}
            >
              {shortLabel(type.label)}
            </button>
          ))}
        </div>
        <div className="toolbar filter-pills">
          <SelectField label="Status" value={f.status} onChange={(e) => filters.update({ status: e.target.value })}>
            <option value="">All statuses</option>
            {ALL_STATUSES.map((status) => (
              <option key={status} value={status}>
                {STATUS_LABELS[status]}
              </option>
            ))}
          </SelectField>
          <ScopeFilters options={options} values={scope} onChange={filters.update} />
          {filters.active && (
            <Button type="button" variant="link" onClick={filters.clear}>
              Clear filters
            </Button>
          )}
        </div>
      </form>
      {options.error && <p className="muted small">Filter options could not be loaded.</p>}

      {summary.error ? (
        <ErrorState message={summary.error} onRetry={summary.retry} />
      ) : (
        <div className="kpi-grid" aria-label="Key figures">
          <KpiCard
            hero
            icon="package"
            label="Total Products in Stock"
            value={s?.total_products_in_stock}
            detail="Products with stock on hand"
            to={stockLink("IN_STOCK,LOW_STOCK")}
            loading={summary.loading}
          />
          <KpiCard
            icon="alert"
            label="Low / Out of Stock"
            value={s ? s.low_stock_items + s.out_of_stock_items : null}
            detail={s ? `${s.low_stock_items} low · ${s.out_of_stock_items} out of stock` : undefined}
            to={stockLink("LOW_STOCK,OUT_OF_STOCK")}
            loading={summary.loading}
          />
          <KpiCard
            icon="inbox"
            label={statusLabel ? `Receipts · ${statusLabel}` : "Pending Receipts"}
            value={s?.pending_receipts}
            detail={statusLabel ? undefined : "Draft, waiting or ready"}
            to={operationLink("/receipts")}
            loading={summary.loading}
            disabledReason={excluded("RECEIPT")}
          />
          <KpiCard
            icon="truck"
            label={statusLabel ? `Deliveries · ${statusLabel}` : "Pending Deliveries"}
            value={s?.pending_deliveries}
            detail={statusLabel ? undefined : "Draft, waiting or ready"}
            to={operationLink("/deliveries")}
            loading={summary.loading}
            disabledReason={excluded("DELIVERY")}
          />
          <KpiCard
            icon="transfer"
            label={statusLabel ? `Transfers · ${statusLabel}` : "Internal Transfers Scheduled"}
            value={s?.scheduled_transfers}
            detail={statusLabel ? undefined : "Not yet done or canceled"}
            to={operationLink("/transfers")}
            loading={summary.loading}
            disabledReason={excluded("TRANSFER")}
          />
        </div>
      )}

      <div className="dashboard-grid">
        <section className="card" aria-labelledby="operations-title">
          <div className="section-header compact">
            <div>
              <h2 id="operations-title">Operations by status</h2>
              <p className="muted small">Documents per type and where they are in the flow.</p>
            </div>
          </div>
          {summary.loading && <p className="muted">Loading operations…</p>}
          {s && s.documents.every((d) => d.total === 0) && <EmptyState>No documents match these filters.</EmptyState>}
          {s && s.documents.some((d) => d.total > 0) && (
            <>
              <BarChart
                legend={CHART_LEGEND}
                columns={s.documents.map((doc) => ({
                  label: shortLabel(DOCUMENT_TYPES.find((t) => t.value === doc.document_type)!.label),
                  highlighted: f.document_type === doc.document_type,
                  segments: [
                    { key: "done", value: doc.counts.DONE ?? 0 },
                    { key: "open", value: OPEN.reduce((sum, status) => sum + (doc.counts[status] ?? 0), 0) },
                    { key: "canceled", value: doc.counts.CANCELED ?? 0 },
                  ],
                }))}
              />
              <div className="table-wrap flush">
                <table className="table table-compact">
                  <thead>
                    <tr>
                      <th>Document type</th>
                      {(f.status ? [f.status as DocumentStatus] : ALL_STATUSES).map((status) => (
                        <th key={status} className="num">
                          {STATUS_LABELS[status]}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {s.documents.map((doc) => {
                      const type = DOCUMENT_TYPES.find((t) => t.value === doc.document_type)!;
                      return (
                        <tr key={doc.document_type}>
                          <th scope="row">
                            <Link to={type.path}>{type.label}</Link>
                          </th>
                          {Object.entries(doc.counts).map(([status, count]) => (
                            <td key={status} className="num">
                              {count ? (
                                <Link to={`${type.path}${query({ status, warehouse_id: f.warehouse_id })}`}>{count}</Link>
                              ) : (
                                <span className="muted">0</span>
                              )}
                            </td>
                          ))}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>

        <section className="card alerts-card" aria-labelledby="alerts-title">
          <div className="section-header compact">
            <h2 id="alerts-title">Stock alerts</h2>
            <Link to={stockLink("LOW_STOCK,OUT_OF_STOCK")} className="pill-link">
              View all
            </Link>
          </div>
          {alerts.loading && <p className="muted">Loading inventory…</p>}
          {alerts.error && <ErrorState message={alerts.error} onRetry={alerts.retry} />}
          {alerts.data && alerts.data.items.length === 0 && <EmptyState>No low-stock or out-of-stock items.</EmptyState>}
          {alerts.data && alerts.data.items.length > 0 && (
            <ul className="alert-list">
              {alerts.data.items.map((row) => (
                <li key={`${row.product.id}-${row.location.id}`}>
                  <Thumb name={row.product.name} />
                  <span className="alert-item-text">
                    <Link to={`/products/${row.product.id}`}>{row.product.name}</Link>
                    <span className="muted small">
                      {locationLabel(row.location)} · {formatQuantity(row.quantity, row.product.unit_of_measure.symbol)} on hand
                      {row.minimum_quantity !== null && ` (min ${formatQuantity(row.minimum_quantity)})`}
                    </span>
                  </span>
                  <StockStatusBadge status={row.status} />
                </li>
              ))}
            </ul>
          )}
          {alerts.data && alerts.data.total > alerts.data.items.length && (
            <p className="muted small">+{alerts.data.total - alerts.data.items.length} more</p>
          )}
          {progress && (
            <div className="inset-card">
              <div>
                <p className="inset-title">Documents completed</p>
                <p className="muted small inset-detail">
                  <Icon name="check" size={14} />
                  {progress.countable
                    ? `${progress.done} of ${progress.countable} done (canceled excluded)`
                    : "No documents yet"}
                </p>
              </div>
              <Donut percent={progress.percent} label="Documents completed" />
            </div>
          )}
        </section>
      </div>

      <section className="card activity-card" aria-labelledby="activity-title">
        <div className="section-header compact">
          <h2 id="activity-title">Recent activity</h2>
          <div className="card-actions">
            <button type="button" className="icon-button" onClick={activity.retry} aria-label="Reload recent activity" title="Reload">
              <Icon name="rotate" />
            </button>
            <Link
              to={`/move-history${query({ ...scope, movement_type: f.document_type })}`}
              className="icon-button"
              aria-label="Open move history"
              title="Open move history"
            >
              <Icon name="arrowUpRight" />
            </Link>
          </div>
        </div>
        {f.status && <p className="muted small">Stock only moves when a document is done, so the status filter does not apply here.</p>}
        {activity.loading && <p className="muted">Loading recent movements…</p>}
        {activity.error && <ErrorState message={activity.error} onRetry={activity.retry} />}
        {activity.data && activity.data.items.length === 0 && <EmptyState>No stock movements yet.</EmptyState>}
        {activity.data && activity.data.items.length > 0 && <MovementTable movements={activity.data.items} compact />}
      </section>
    </section>
  );
}

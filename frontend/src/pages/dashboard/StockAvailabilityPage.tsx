import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Button } from "../../components/ui/Button";
import { SelectField, TextField } from "../../components/ui/FormField";
import { PageHeader } from "../../components/ui/PageHeader";
import { Pagination } from "../../components/ui/Pagination";
import { dashboardApi, splitList } from "../../modules/dashboard/api";
import {
  EmptyState,
  ErrorState,
  ScopeFilters,
  StockStatusBadge,
  useFilterOptions,
} from "../../modules/dashboard/components";
import { useApiData, useUrlFilters } from "../../modules/dashboard/hooks";
import { formatQuantity } from "../../modules/inventory/operations";
import { useDebouncedValue } from "../../modules/master-data/hooks";

const FILTER_KEYS = ["q", "status", "warehouse_id", "location_id", "category_id", "offset"] as const;
const PAGE_SIZE = 25;

const STATUS_OPTIONS = [
  { value: "", label: "All" },
  { value: "IN_STOCK,LOW_STOCK", label: "In stock (incl. low)" },
  { value: "LOW_STOCK,OUT_OF_STOCK", label: "Low or out of stock" },
  { value: "LOW_STOCK", label: "Low stock" },
  { value: "OUT_OF_STOCK", label: "Out of stock" },
  { value: "IN_STOCK", label: "In stock (above minimum)" },
];

/** Read-only view of Ravi's stock with a status from Gautam's reorder rules. */
export function StockAvailabilityPage() {
  const filters = useUrlFilters(FILTER_KEYS);
  const f = filters.values;
  const options = useFilterOptions();
  const [search, setSearch] = useState(f.q);
  const q = useDebouncedValue(search.trim());
  useEffect(() => {
    if (q !== f.q) filters.update({ q, offset: "" });
  }, [q]);

  const { data, loading, error, retry } = useApiData(
    (params, signal) => dashboardApi.availability({ ...params, status: splitList(params.status), limit: PAGE_SIZE }, signal),
    { q: f.q, status: f.status, warehouse_id: f.warehouse_id, location_id: f.location_id, category_id: f.category_id, offset: f.offset },
  );
  const knownStatus = STATUS_OPTIONS.some((o) => o.value === f.status);

  return (
    <section className="page page-wide">
      <PageHeader
        title="Stock Availability"
        description="Current stock by product and location. Low stock means at or below the reorder rule minimum."
      />
      <form className="toolbar filter-bar" aria-label="Stock filters" onSubmit={(e) => e.preventDefault()}>
        <TextField label="Search" type="search" placeholder="Product name or SKU" value={search} onChange={(e) => setSearch(e.target.value)} />
        <SelectField label="Stock status" value={knownStatus ? f.status : ""} onChange={(e) => filters.update({ status: e.target.value, offset: "" })}>
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </SelectField>
        <ScopeFilters options={options} values={f} onChange={(changes) => filters.update({ ...changes, offset: "" })} />
        {filters.active && (
          <Button
            type="button"
            variant="link"
            onClick={() => {
              setSearch("");
              filters.clear();
            }}
          >
            Clear filters
          </Button>
        )}
      </form>

      {error && <ErrorState message={error} onRetry={retry} />}
      {!error && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Product</th>
                <th>SKU</th>
                <th>Category</th>
                <th>Warehouse</th>
                <th>Location</th>
                <th className="num">On hand</th>
                <th className="num">Minimum</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map((row) => (
                <tr key={`${row.product.id}-${row.location.id}`}>
                  <td>
                    <Link to={`/products/${row.product.id}`}>{row.product.name}</Link>
                  </td>
                  <td className="mono">{row.product.sku}</td>
                  <td>{row.category.name}</td>
                  <td>{row.location.warehouse.name}</td>
                  <td>{row.location.name}</td>
                  <td className="num">{formatQuantity(row.quantity, row.product.unit_of_measure.symbol)}</td>
                  <td className="num">{row.minimum_quantity === null ? "—" : formatQuantity(row.minimum_quantity)}</td>
                  <td>
                    <StockStatusBadge status={row.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {loading && <p className="muted table-message">Loading inventory…</p>}
          {!loading && data?.items.length === 0 && (
            <EmptyState>{filters.active ? "No stock matches these filters." : "No products in stock yet."}</EmptyState>
          )}
        </div>
      )}
      {data && (
        <Pagination total={data.total} limit={data.limit} offset={data.offset} onChange={(offset) => filters.update({ offset: offset ? String(offset) : "" })} />
      )}
    </section>
  );
}

import { useEffect, useState } from "react";

import { Button } from "../../components/ui/Button";
import { SelectField, TextField } from "../../components/ui/FormField";
import { PageHeader } from "../../components/ui/PageHeader";
import { Pagination } from "../../components/ui/Pagination";
import {
  EmptyState,
  ErrorState,
  MOVEMENT_LABELS,
  MovementTable,
  ScopeFilters,
  useFilterOptions,
} from "../../modules/dashboard/components";
import { useApiData, useUrlFilters } from "../../modules/dashboard/hooks";
import { stockApi } from "../../modules/inventory/api";
import { useDebouncedValue } from "../../modules/master-data/hooks";

const FILTER_KEYS = [
  "q",
  "movement_type",
  "warehouse_id",
  "location_id",
  "category_id",
  "product_id",
  "date_from",
  "date_to",
  "offset",
] as const;
const PAGE_SIZE = 25;

/** Stock ledger: every stock movement recorded by the inventory engine, newest first. */
export function MoveHistoryPage() {
  const filters = useUrlFilters(FILTER_KEYS);
  const f = filters.values;
  const options = useFilterOptions();
  const [search, setSearch] = useState(f.q);
  const q = useDebouncedValue(search.trim());
  useEffect(() => {
    if (q !== f.q) filters.update({ q, offset: "" });
  }, [q]);

  const invalidRange = Boolean(f.date_from && f.date_to && f.date_from > f.date_to);
  const { data, loading, error, retry } = useApiData(
    (params, signal) => stockApi.movements({ ...params, limit: PAGE_SIZE }, signal),
    invalidRange ? { ...f, date_to: "" } : { ...f },
  );
  const set = (changes: Partial<Record<(typeof FILTER_KEYS)[number], string>>) => filters.update({ ...changes, offset: "" });

  return (
    <section className="page page-wide">
      <PageHeader
        title="Move History"
        description="The stock ledger: every receipt, delivery, transfer and adjustment that changed stock."
      />
      <form className="toolbar filter-bar" aria-label="Move history filters" onSubmit={(e) => e.preventDefault()}>
        <TextField
          label="Search"
          type="search"
          placeholder="Product, SKU or reference"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <SelectField label="Movement type" value={f.movement_type} onChange={(e) => set({ movement_type: e.target.value })}>
          <option value="">All</option>
          {Object.entries(MOVEMENT_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </SelectField>
        <ScopeFilters options={options} values={f} onChange={set} />
        <TextField label="From date" type="date" value={f.date_from} onChange={(e) => set({ date_from: e.target.value })} />
        <TextField
          label="To date"
          type="date"
          value={f.date_to}
          onChange={(e) => set({ date_to: e.target.value })}
          error={invalidRange ? "Must be on or after the From date" : undefined}
        />
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
      {f.product_id && (
        <p className="filter-chip">
          Showing one product only.{" "}
          <button type="button" className="link-button" onClick={() => set({ product_id: "" })}>
            Show all products
          </button>
        </p>
      )}

      {error && <ErrorState message={error} onRetry={retry} />}
      {loading && <p className="muted">Loading ledger…</p>}
      {!loading && !error && data?.items.length === 0 && (
        <EmptyState>{filters.active ? "No movements match these filters." : "No stock movements yet."}</EmptyState>
      )}
      {!error && data && data.items.length > 0 && <MovementTable movements={data.items} />}
      {data && (
        <Pagination total={data.total} limit={data.limit} offset={data.offset} onChange={(offset) => filters.update({ offset: offset ? String(offset) : "" })} />
      )}
    </section>
  );
}

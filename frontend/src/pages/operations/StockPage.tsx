import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Alert } from "../../components/ui/Alert";
import { SelectField, TextField } from "../../components/ui/FormField";
import { PageHeader } from "../../components/ui/PageHeader";
import { Pagination } from "../../components/ui/Pagination";
import { stockApi } from "../../modules/inventory/api";
import { formatDateTime, formatQuantity } from "../../modules/inventory/operations";
import type { StockPosition } from "../../modules/inventory/types";
import { ALL, warehousesApi } from "../../modules/master-data/api";
import { useDebouncedValue, usePagedList } from "../../modules/master-data/hooks";
import type { Warehouse } from "../../modules/master-data/types";

export function StockPage() {
  const [search, setSearch] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [offset, setOffset] = useState(0);
  const q = useDebouncedValue(search.trim());
  const { data, loading, error } = usePagedList<StockPosition>(stockApi.list, {
    q,
    warehouse_id: warehouseId,
    limit: 50,
    offset,
  });

  useEffect(() => {
    warehousesApi.list({ limit: ALL }).then((page) => setWarehouses(page.items)).catch(() => setWarehouses([]));
  }, []);

  return (
    <section className="page page-wide">
      <PageHeader title="Stock" description="Current on-hand quantity of each product at each location." />
      <div className="toolbar">
        <TextField
          label="Search"
          type="search"
          placeholder="Product name or SKU"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setOffset(0);
          }}
        />
        <SelectField
          label="Warehouse"
          value={warehouseId}
          onChange={(e) => {
            setWarehouseId(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">All warehouses</option>
          {warehouses.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </SelectField>
      </div>

      {error && <Alert variant="error">{error}</Alert>}
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Product</th>
              <th>SKU</th>
              <th>Warehouse</th>
              <th>Location</th>
              <th className="num">On hand</th>
              <th>Last change</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((row) => (
              <tr key={row.id}>
                <td>
                  <Link to={`/products/${row.product_id}`}>{row.product.name}</Link>
                </td>
                <td className="mono">{row.product.sku}</td>
                <td>{row.location.warehouse.name}</td>
                <td>{row.location.name}</td>
                <td className="num">{formatQuantity(row.quantity, row.product.unit_of_measure.symbol)}</td>
                <td className="muted small">{formatDateTime(row.updated_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {loading && <p className="muted table-message">Loading…</p>}
        {!loading && data?.items.length === 0 && <p className="muted table-message">No stock found.</p>}
      </div>
      {data && <Pagination total={data.total} limit={data.limit} offset={data.offset} onChange={setOffset} />}
    </section>
  );
}

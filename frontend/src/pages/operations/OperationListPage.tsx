import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { SelectField, TextField } from "../../components/ui/FormField";
import { PageHeader } from "../../components/ui/PageHeader";
import { Pagination } from "../../components/ui/Pagination";
import { operationApi } from "../../modules/inventory/api";
import { DocumentStatusBadge } from "../../modules/inventory/DocumentStatusBadge";
import { formatDateTime, STATUS_LABELS, type OperationConfig } from "../../modules/inventory/operations";
import { OPEN_STATUSES, type InventoryDocument } from "../../modules/inventory/types";
import { ALL, warehousesApi } from "../../modules/master-data/api";
import { useDebouncedValue, usePagedList } from "../../modules/master-data/hooks";
import type { Warehouse } from "../../modules/master-data/types";

const PENDING = "PENDING";

export function OperationListPage({ config }: { config: OperationConfig }) {
  const navigate = useNavigate();
  const api = operationApi(config.kind);
  const [searchParams] = useSearchParams();
  // Initial filters may come from the URL (e.g. dashboard links: ?status=READY&warehouse_id=2).
  const [status, setStatus] = useState<string>(searchParams.get("status") ?? PENDING);
  const [search, setSearch] = useState("");
  const [warehouseId, setWarehouseId] = useState(searchParams.get("warehouse_id") ?? "");
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [offset, setOffset] = useState(0);
  const q = useDebouncedValue(search.trim());

  const { data, loading, error } = usePagedList<InventoryDocument>(
    // The list hook takes flat params; statuses travel comma-joined and are sent as repeated ?status=.
    (params, signal) => api.list({ ...params, status: params.status ? String(params.status).split(",") : undefined }, signal),
    {
      status: status === PENDING ? OPEN_STATUSES.join(",") : status,
      q,
      warehouse_id: warehouseId,
      limit: 20,
      offset,
    },
  );

  useEffect(() => {
    warehousesApi.list({ limit: ALL }).then((page) => setWarehouses(page.items)).catch(() => setWarehouses([]));
  }, []);

  return (
    <section className="page page-wide">
      <PageHeader
        title={config.title}
        description={config.description}
        actions={
          <Button type="button" onClick={() => navigate(`/${config.kind}/new`)}>
            New {config.singular}
          </Button>
        }
      />

      <div className="toolbar">
        <SelectField
          label="Status"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setOffset(0);
          }}
        >
          <option value={PENDING}>Pending (Draft, Waiting, Ready)</option>
          <option value="">All</option>
          {Object.entries(STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </SelectField>
        <TextField
          label="Search"
          type="search"
          placeholder="Reference or name"
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
              <th>Reference</th>
              <th>Details</th>
              <th>Lines</th>
              <th>Scheduled</th>
              <th>Status</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((doc) => (
              <tr key={doc.id}>
                <td>
                  <Link to={`/${config.kind}/${doc.id}`} className="mono">
                    {doc.reference}
                  </Link>
                </td>
                <td>{config.summary(doc)}</td>
                <td>{doc.items.length}</td>
                <td>{doc.scheduled_date ?? "—"}</td>
                <td>
                  <DocumentStatusBadge status={doc.status} />
                </td>
                <td className="muted small">{formatDateTime(doc.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {loading && <p className="muted table-message">Loading…</p>}
        {!loading && data?.items.length === 0 && (
          <p className="muted table-message">No {config.title.toLowerCase()} found.</p>
        )}
      </div>
      {data && <Pagination total={data.total} limit={data.limit} offset={data.offset} onChange={setOffset} />}
    </section>
  );
}

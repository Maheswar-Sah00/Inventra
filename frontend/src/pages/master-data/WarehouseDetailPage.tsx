import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Alert } from "../../components/ui/Alert";
import { PageHeader } from "../../components/ui/PageHeader";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { warehousesApi } from "../../modules/master-data/api";
import { LocationsManager } from "../../modules/master-data/LocationsManager";
import type { Warehouse } from "../../modules/master-data/types";
import { ApiError } from "../../services/apiClient";

export function WarehouseDetailPage() {
  const id = Number(useParams().id);
  const [warehouse, setWarehouse] = useState<Warehouse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    warehousesApi
      .get(id, controller.signal)
      .then(setWarehouse)
      .catch((err: Error) => {
        if (err.name !== "AbortError") setError(err instanceof ApiError ? err.message : "Unable to load the warehouse.");
      });
    return () => controller.abort();
  }, [id]);

  if (error) return <Alert variant="error">{error}</Alert>;
  if (!warehouse) return <p className="muted">Loading…</p>;

  return (
    <section className="page page-wide">
      <p className="breadcrumb">
        <Link to="/warehouses">Warehouses</Link> / {warehouse.name}
      </p>
      <PageHeader title={warehouse.name} />
      <div className="card">
        <dl className="details">
          <dt>Code</dt>
          <dd className="mono">{warehouse.code}</dd>
          <dt>Address</dt>
          <dd>{warehouse.address ?? "—"}</dd>
          <dt>Status</dt>
          <dd>
            <StatusBadge active={warehouse.is_active} />
          </dd>
        </dl>
      </div>
      <LocationsManager warehouseId={warehouse.id} />
    </section>
  );
}

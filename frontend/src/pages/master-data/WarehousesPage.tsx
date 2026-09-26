import { Link } from "react-router-dom";

import { warehousesApi } from "../../modules/master-data/api";
import { SimpleEntityPage } from "../../modules/master-data/SimpleEntityPage";
import type { Warehouse } from "../../modules/master-data/types";

export function WarehousesPage() {
  return (
    <SimpleEntityPage<Warehouse>
      title="Warehouses"
      singular="warehouse"
      description="Sites that hold stock. Open a warehouse to manage its locations."
      api={warehousesApi}
      searchPlaceholder="Search by name or code"
      fields={[
        { name: "name", label: "Name", required: true, maxLength: 100 },
        { name: "code", label: "Code", kind: "code", maxLength: 32, hint: "Short unique code, e.g. WH-MAIN" },
        { name: "address", label: "Address", maxLength: 500 },
      ]}
      columns={[
        { header: "Name", render: (w) => <Link to={`/warehouses/${w.id}`}>{w.name}</Link> },
        { header: "Code", render: (w) => <span className="mono">{w.code}</span> },
        { header: "Address", render: (w) => w.address ?? <span className="muted">—</span> },
      ]}
    />
  );
}

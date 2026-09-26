import { unitsApi } from "../../modules/master-data/api";
import { SimpleEntityPage } from "../../modules/master-data/SimpleEntityPage";
import type { Unit } from "../../modules/master-data/types";

export function UnitsPage() {
  return (
    <SimpleEntityPage<Unit>
      title="Units of Measure"
      singular="unit"
      description="How product quantities are counted, e.g. Kilogram (kg) or Piece (pc)."
      api={unitsApi}
      searchPlaceholder="Search by name or symbol"
      fields={[
        { name: "name", label: "Name", required: true, maxLength: 50 },
        { name: "symbol", label: "Symbol", required: true, maxLength: 16 },
      ]}
      columns={[
        { header: "Name", render: (u) => u.name },
        { header: "Symbol", render: (u) => <span className="mono">{u.symbol}</span> },
      ]}
    />
  );
}

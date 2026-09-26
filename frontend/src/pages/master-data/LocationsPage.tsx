import { PageHeader } from "../../components/ui/PageHeader";
import { LocationsManager } from "../../modules/master-data/LocationsManager";

export function LocationsPage() {
  return (
    <section className="page page-wide">
      <PageHeader
        title="Locations"
        description="Racks, shelves and zones inside each warehouse. Stock is stored and moved between locations."
      />
      <LocationsManager />
    </section>
  );
}

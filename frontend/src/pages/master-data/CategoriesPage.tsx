import { categoriesApi } from "../../modules/master-data/api";
import { SimpleEntityPage } from "../../modules/master-data/SimpleEntityPage";
import type { Category } from "../../modules/master-data/types";

export function CategoriesPage() {
  return (
    <SimpleEntityPage<Category>
      title="Categories"
      singular="category"
      description="Group products for filtering and reporting."
      api={categoriesApi}
      searchPlaceholder="Search categories"
      fields={[
        { name: "name", label: "Name", required: true, maxLength: 100 },
        { name: "description", label: "Description", maxLength: 500 },
      ]}
      columns={[
        { header: "Name", render: (c) => c.name },
        { header: "Description", render: (c) => c.description ?? <span className="muted">—</span> },
      ]}
    />
  );
}

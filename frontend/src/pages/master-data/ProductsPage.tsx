import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { SelectField, TextField } from "../../components/ui/FormField";
import { PageHeader } from "../../components/ui/PageHeader";
import { Pagination } from "../../components/ui/Pagination";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { useAuth } from "../../modules/auth";
import { ALL, categoriesApi, productsApi } from "../../modules/master-data/api";
import { useDebouncedValue, usePagedList } from "../../modules/master-data/hooks";
import { StatusFilterSelect, statusParam, type StatusFilter } from "../../modules/master-data/SimpleEntityPage";
import type { Category, Product } from "../../modules/master-data/types";

export function ProductsPage() {
  const { hasRole } = useAuth();
  const navigate = useNavigate();
  const [categories, setCategories] = useState<Category[]>([]);
  const [search, setSearch] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [status, setStatus] = useState<StatusFilter>("active");
  const [offset, setOffset] = useState(0);
  const q = useDebouncedValue(search.trim());

  const { data, loading, error } = usePagedList<Product>(productsApi.list, {
    q,
    category_id: categoryId,
    is_active: statusParam(status),
    limit: 20,
    offset,
  });

  useEffect(() => {
    categoriesApi
      .list({ limit: ALL })
      .then((page) => setCategories(page.items))
      .catch(() => setCategories([]));
  }, []);

  return (
    <section className="page page-wide">
      <PageHeader
        title="Products"
        description="Everything you stock, with SKU, category and unit of measure."
        actions={
          hasRole("INVENTORY_MANAGER") ? (
            <Button type="button" onClick={() => navigate("/products/new")}>
              New product
            </Button>
          ) : undefined
        }
      />

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
          label="Category"
          value={categoryId}
          onChange={(e) => {
            setCategoryId(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
              {c.is_active ? "" : " (inactive)"}
            </option>
          ))}
        </SelectField>
        <StatusFilterSelect
          value={status}
          onChange={(value) => {
            setStatus(value);
            setOffset(0);
          }}
        />
      </div>

      {error && <Alert variant="error">{error}</Alert>}
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>SKU</th>
              <th>Category</th>
              <th>Unit</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((product) => (
              <tr key={product.id}>
                <td>
                  <Link to={`/products/${product.id}`}>{product.name}</Link>
                </td>
                <td className="mono">{product.sku}</td>
                <td>{product.category.name}</td>
                <td>{product.unit_of_measure.symbol}</td>
                <td>
                  <StatusBadge active={product.is_active} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {loading && <p className="muted table-message">Loading…</p>}
        {!loading && data?.items.length === 0 && <p className="muted table-message">No products found.</p>}
      </div>
      {data && <Pagination total={data.total} limit={data.limit} offset={data.offset} onChange={setOffset} />}
    </section>
  );
}

import { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { PageHeader } from "../../components/ui/PageHeader";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { useAuth } from "../../modules/auth";
import { ProductStockPanel } from "../../modules/inventory/ProductStockPanel";
import { productsApi, reorderRulesApi } from "../../modules/master-data/api";
import { locationLabel, type Product, type ReorderRule } from "../../modules/master-data/types";
import { ApiError } from "../../services/apiClient";

export function ProductDetailPage() {
  const id = Number(useParams().id);
  const { hasRole } = useAuth();
  const canManage = hasRole("INVENTORY_MANAGER");
  const navigate = useNavigate();
  const location = useLocation();

  const [product, setProduct] = useState<Product | null>(null);
  const [rules, setRules] = useState<ReorderRule[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>((location.state as { message?: string } | null)?.message ?? null);
  const [toggling, setToggling] = useState(false);

  const load = useCallback(
    (signal?: AbortSignal) =>
      Promise.all([productsApi.get(id, signal), reorderRulesApi.list({ product_id: id, limit: 100 }, signal)])
        .then(([p, r]) => {
          setProduct(p);
          setRules(r.items);
        })
        .catch((err: Error) => {
          if (err.name !== "AbortError") setError(err instanceof ApiError ? err.message : "Unable to load the product.");
        }),
    [id],
  );

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  async function toggleActive() {
    if (!product) return;
    setToggling(true);
    setError(null);
    try {
      const updated = await productsApi.update(product.id, { is_active: !product.is_active });
      setProduct(updated);
      setNotice(updated.is_active ? "Product activated." : "Product deactivated.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to update the product.");
    } finally {
      setToggling(false);
    }
  }

  if (error && !product) return <Alert variant="error">{error}</Alert>;
  if (!product) return <p className="muted">Loading…</p>;

  return (
    <section className="page page-wide">
      <p className="breadcrumb">
        <Link to="/products">Products</Link> / {product.name}
      </p>
      <PageHeader
        title={product.name}
        actions={
          canManage ? (
            <>
              <Button type="button" onClick={() => navigate(`/products/${product.id}/edit`)}>
                Edit
              </Button>
              <Button type="button" variant="secondary" onClick={toggleActive} loading={toggling}>
                {product.is_active ? "Deactivate" : "Activate"}
              </Button>
            </>
          ) : undefined
        }
      />
      {notice && <Alert variant="success">{notice}</Alert>}
      {error && <Alert variant="error">{error}</Alert>}

      <div className="card">
        <dl className="details">
          <dt>SKU / Code</dt>
          <dd className="mono">{product.sku}</dd>
          <dt>Category</dt>
          <dd>{product.category.name}</dd>
          <dt>Unit of measure</dt>
          <dd>
            {product.unit_of_measure.name} ({product.unit_of_measure.symbol})
          </dd>
          <dt>Initial stock</dt>
          <dd>
            {product.initial_stock > 0 && product.initial_location
              ? `${product.initial_stock} ${product.unit_of_measure.symbol} at ${locationLabel(product.initial_location)}`
              : "None"}
          </dd>
          <dt>Status</dt>
          <dd>
            <StatusBadge active={product.is_active} />
          </dd>
        </dl>
      </div>

      <ProductStockPanel productId={product.id} />

      <div className="section-header">
        <h2>Reordering rules</h2>
        <Link to={`/reorder-rules?product_id=${product.id}`}>{canManage ? "Manage rules" : "View rules"}</Link>
      </div>
      {rules.length === 0 ? (
        <p className="muted">No reordering rules for this product.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Location</th>
                <th>Minimum</th>
                <th>Target</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => (
                <tr key={rule.id}>
                  <td>{locationLabel(rule.location)}</td>
                  <td>{rule.minimum_quantity}</td>
                  <td>{rule.target_quantity}</td>
                  <td>
                    <StatusBadge active={rule.is_active} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

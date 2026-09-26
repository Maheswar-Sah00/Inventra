import { useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { CheckboxField } from "../../components/ui/CheckboxField";
import { SelectField, TextField } from "../../components/ui/FormField";
import { PageHeader } from "../../components/ui/PageHeader";
import { Pagination } from "../../components/ui/Pagination";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { useAuth } from "../../modules/auth";
import { ALL, locationsApi, productsApi, reorderRulesApi, warehousesApi } from "../../modules/master-data/api";
import { usePagedList } from "../../modules/master-data/hooks";
import { StatusFilterSelect, statusParam, type StatusFilter } from "../../modules/master-data/SimpleEntityPage";
import { locationLabel, type Location, type Product, type ReorderRule, type Warehouse } from "../../modules/master-data/types";
import { requiredSelection, validateQuantity, validateTarget } from "../../modules/master-data/validation";
import { ApiError } from "../../services/apiClient";

type FormState = {
  product_id: string;
  location_id: string;
  minimum_quantity: string;
  target_quantity: string;
  is_active: boolean;
};

export function ReorderRulesPage() {
  const { hasRole } = useAuth();
  const canManage = hasRole("INVENTORY_MANAGER");
  const [searchParams, setSearchParams] = useSearchParams();
  const productFilter = searchParams.get("product_id") ?? "";

  const [products, setProducts] = useState<Product[]>([]);
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [warehouseFilter, setWarehouseFilter] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [offset, setOffset] = useState(0);

  const { data, loading, error, reload } = usePagedList<ReorderRule>(reorderRulesApi.list, {
    product_id: productFilter,
    warehouse_id: warehouseFilter,
    is_active: statusParam(status),
    limit: 20,
    offset,
  });

  useEffect(() => {
    productsApi.list({ limit: ALL }).then((p) => setProducts(p.items)).catch(() => setProducts([]));
    warehousesApi.list({ limit: ALL }).then((p) => setWarehouses(p.items)).catch(() => setWarehouses([]));
    locationsApi.list({ limit: ALL }).then((p) => setLocations(p.items)).catch(() => setLocations([]));
  }, []);

  const [editing, setEditing] = useState<ReorderRule | "new" | null>(null);
  const [form, setForm] = useState<FormState>({ product_id: "", location_id: "", minimum_quantity: "", target_quantity: "", is_active: true });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function openForm(item: ReorderRule | "new") {
    setForm(
      item === "new"
        ? { product_id: productFilter, location_id: "", minimum_quantity: "", target_quantity: "", is_active: true }
        : {
            product_id: String(item.product_id),
            location_id: String(item.location_id),
            minimum_quantity: String(item.minimum_quantity),
            target_quantity: String(item.target_quantity),
            is_active: item.is_active,
          },
    );
    setErrors({});
    setFormError(null);
    setNotice(null);
    setEditing(item);
  }

  const update = (field: keyof FormState) => (event: { target: { value: string } }) =>
    setForm((current) => ({ ...current, [field]: event.target.value }));

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const checks: Record<string, string | null> = {
      minimum_quantity: validateQuantity(form.minimum_quantity, "Minimum quantity"),
      target_quantity: validateTarget(form.minimum_quantity, form.target_quantity),
    };
    if (editing === "new") {
      checks.product_id = requiredSelection(form.product_id, "product");
      checks.location_id = requiredSelection(form.location_id, "location");
    }
    const found = Object.fromEntries(Object.entries(checks).filter((e): e is [string, string] => e[1] !== null));
    setErrors(found);
    setFormError(null);
    if (Object.keys(found).length || editing === null) return;

    const quantities = {
      minimum_quantity: form.minimum_quantity.trim(),
      target_quantity: form.target_quantity.trim(),
      is_active: form.is_active,
    };
    setSaving(true);
    try {
      if (editing === "new") {
        await reorderRulesApi.create({ ...quantities, product_id: Number(form.product_id), location_id: Number(form.location_id) });
      } else {
        await reorderRulesApi.update(editing.id, quantities);
      }
      setNotice(editing === "new" ? "Reorder rule created." : "Reorder rule updated.");
      setEditing(null);
      reload();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Unable to save the reorder rule.");
      if (err instanceof ApiError) setErrors(err.fieldErrors);
    } finally {
      setSaving(false);
    }
  }

  async function runAction(action: () => Promise<unknown>, message: string) {
    setNotice(null);
    setFormError(null);
    try {
      await action();
      setNotice(message);
      reload();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Unable to update the reorder rule.");
    }
  }

  function remove(rule: ReorderRule) {
    if (!window.confirm(`Delete the reorder rule for ${rule.product.name} at ${locationLabel(rule.location)}?`)) return;
    runAction(() => reorderRulesApi.remove(rule.id), "Reorder rule deleted.");
  }

  const activeProducts = products.filter((p) => p.is_active);
  const usableLocations = locations.filter((l) => l.is_active && l.warehouse.is_active);

  return (
    <section className="page page-wide">
      <PageHeader
        title="Reordering Rules"
        description="When stock at a location falls to the minimum, the product should be replenished up to the target."
        actions={
          canManage && editing === null ? (
            <Button type="button" onClick={() => openForm("new")}>
              New rule
            </Button>
          ) : undefined
        }
      />
      {notice && <Alert variant="success">{notice}</Alert>}
      {formError && editing === null && <Alert variant="error">{formError}</Alert>}

      {editing !== null && (
        <form className="card form-card" onSubmit={handleSubmit} noValidate aria-label="reorder rule form">
          <h2>{editing === "new" ? "New reorder rule" : "Edit reorder rule"}</h2>
          {formError && <Alert variant="error">{formError}</Alert>}
          <div className="form-grid">
            {editing === "new" ? (
              <>
                <SelectField label="Product" value={form.product_id} onChange={update("product_id")} error={errors.product_id}>
                  <option value="">Select a product</option>
                  {activeProducts.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.sku})
                    </option>
                  ))}
                </SelectField>
                <SelectField label="Location" value={form.location_id} onChange={update("location_id")} error={errors.location_id}>
                  <option value="">Select a location</option>
                  {usableLocations.map((l) => (
                    <option key={l.id} value={l.id}>
                      {locationLabel(l)}
                    </option>
                  ))}
                </SelectField>
              </>
            ) : (
              <p className="form-static">
                <strong>{editing.product.name}</strong> ({editing.product.sku}) at {locationLabel(editing.location)}
              </p>
            )}
            <TextField
              label="Minimum quantity"
              inputMode="decimal"
              value={form.minimum_quantity}
              onChange={update("minimum_quantity")}
              error={errors.minimum_quantity}
              hint="Reorder when stock is at or below this"
            />
            <TextField
              label="Target quantity"
              inputMode="decimal"
              value={form.target_quantity}
              onChange={update("target_quantity")}
              error={errors.target_quantity}
              hint="Replenish up to this level"
            />
          </div>
          <CheckboxField label="Active" checked={form.is_active} onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))} />
          <div className="button-row">
            <Button type="submit" loading={saving} loadingText="Saving…">
              Save
            </Button>
            <Button type="button" variant="secondary" onClick={() => setEditing(null)} disabled={saving}>
              Cancel
            </Button>
          </div>
        </form>
      )}

      <div className="toolbar">
        <SelectField
          label="Product"
          value={productFilter}
          onChange={(e) => {
            setSearchParams(e.target.value ? { product_id: e.target.value } : {});
            setOffset(0);
          }}
        >
          <option value="">All products</option>
          {products.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} ({p.sku})
            </option>
          ))}
        </SelectField>
        <SelectField
          label="Warehouse"
          value={warehouseFilter}
          onChange={(e) => {
            setWarehouseFilter(e.target.value);
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
              <th>Product</th>
              <th>Location</th>
              <th>Minimum</th>
              <th>Target</th>
              <th>Status</th>
              {canManage && <th className="actions-col">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {data?.items.map((rule) => (
              <tr key={rule.id}>
                <td>
                  <Link to={`/products/${rule.product_id}`}>{rule.product.name}</Link>{" "}
                  <span className="muted mono small">{rule.product.sku}</span>
                </td>
                <td>{locationLabel(rule.location)}</td>
                <td>{rule.minimum_quantity}</td>
                <td>{rule.target_quantity}</td>
                <td>
                  <StatusBadge active={rule.is_active} />
                </td>
                {canManage && (
                  <td className="actions-col">
                    <button type="button" className="link-button" onClick={() => openForm(rule)}>
                      Edit
                    </button>
                    <button
                      type="button"
                      className="link-button"
                      onClick={() =>
                        runAction(
                          () => reorderRulesApi.update(rule.id, { is_active: !rule.is_active }),
                          rule.is_active ? "Reorder rule deactivated." : "Reorder rule activated.",
                        )
                      }
                    >
                      {rule.is_active ? "Deactivate" : "Activate"}
                    </button>
                    <button type="button" className="link-button danger" onClick={() => remove(rule)}>
                      Delete
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        {loading && <p className="muted table-message">Loading…</p>}
        {!loading && data?.items.length === 0 && <p className="muted table-message">No reordering rules found.</p>}
      </div>
      {data && <Pagination total={data.total} limit={data.limit} offset={data.offset} onChange={setOffset} />}
    </section>
  );
}

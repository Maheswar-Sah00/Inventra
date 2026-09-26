import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { CheckboxField } from "../../components/ui/CheckboxField";
import { SelectField, TextField } from "../../components/ui/FormField";
import { PageHeader } from "../../components/ui/PageHeader";
import { ALL, categoriesApi, locationsApi, productsApi, unitsApi } from "../../modules/master-data/api";
import { locationLabel, type Category, type Location, type Product, type Unit } from "../../modules/master-data/types";
import {
  requiredSelection,
  requiredText,
  validateCode,
  validateQuantity,
} from "../../modules/master-data/validation";
import { ApiError } from "../../services/apiClient";

type FormState = {
  name: string;
  sku: string;
  category_id: string;
  unit_of_measure_id: string;
  initial_stock: string;
  initial_location_id: string;
  is_active: boolean;
};

const EMPTY: FormState = {
  name: "",
  sku: "",
  category_id: "",
  unit_of_measure_id: "",
  initial_stock: "",
  initial_location_id: "",
  is_active: true,
};

/** Active options plus the currently selected one (which may have been archived since). */
function selectable<T extends { id: number; is_active: boolean }>(items: T[], selectedId: string) {
  return items.filter((item) => item.is_active || String(item.id) === selectedId);
}

export function ProductFormPage() {
  const params = useParams();
  const productId = params.id ? Number(params.id) : null;
  const isEdit = productId !== null;
  const navigate = useNavigate();

  const [form, setForm] = useState<FormState>(EMPTY);
  const [categories, setCategories] = useState<Category[]>([]);
  const [units, setUnits] = useState<Unit[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const requests: Promise<unknown>[] = [
      categoriesApi.list({ limit: ALL }).then((page) => setCategories(page.items)),
      unitsApi.list({ limit: ALL }).then((page) => setUnits(page.items)),
    ];
    if (productId !== null) {
      requests.push(
        productsApi.get(productId).then((product: Product) =>
          setForm({
            ...EMPTY,
            name: product.name,
            sku: product.sku,
            category_id: String(product.category_id),
            unit_of_measure_id: String(product.unit_of_measure_id),
            is_active: product.is_active,
          }),
        ),
      );
    } else {
      requests.push(
        locationsApi
          .list({ limit: ALL, is_active: true })
          .then((page) => setLocations(page.items.filter((l) => l.warehouse.is_active))),
      );
    }
    Promise.all(requests)
      .then(() => setLoaded(true))
      .catch((err) => setLoadError(err instanceof ApiError ? err.message : "Unable to load the form."));
  }, [isEdit, productId]);

  const update = (field: keyof FormState) => (event: { target: { value: string } }) =>
    setForm((current) => ({ ...current, [field]: event.target.value }));

  const hasInitialStock = !isEdit && Number(form.initial_stock) > 0;

  function validate(): Record<string, string> {
    const checks: Record<string, string | null> = {
      name: requiredText(form.name, "Name"),
      sku: validateCode(form.sku, "SKU", 64),
      category_id: requiredSelection(form.category_id, "category"),
      unit_of_measure_id: requiredSelection(form.unit_of_measure_id, "unit of measure"),
    };
    if (!isEdit) {
      checks.initial_stock = validateQuantity(form.initial_stock, "Initial stock", { optional: true });
      if (!checks.initial_stock && hasInitialStock) {
        checks.initial_location_id = requiredSelection(form.initial_location_id, "location for the initial stock");
      }
    }
    return Object.fromEntries(Object.entries(checks).filter((entry): entry is [string, string] => entry[1] !== null));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const found = validate();
    setErrors(found);
    setFormError(null);
    if (Object.keys(found).length) return;

    const common = {
      name: form.name.trim(),
      sku: form.sku.trim(),
      category_id: Number(form.category_id),
      unit_of_measure_id: Number(form.unit_of_measure_id),
    };
    setSaving(true);
    try {
      const saved = productId !== null
        ? await productsApi.update(productId, { ...common, is_active: form.is_active })
        : await productsApi.create({
            ...common,
            initial_stock: form.initial_stock.trim() || "0",
            initial_location_id: hasInitialStock ? Number(form.initial_location_id) : null,
          });
      navigate(`/products/${saved.id}`, { state: { message: isEdit ? "Product updated." : "Product created." } });
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Unable to save the product.");
      if (err instanceof ApiError) setErrors(err.fieldErrors);
      setSaving(false);
    }
  }

  if (loadError) return <Alert variant="error">{loadError}</Alert>;

  return (
    <section className="page">
      <p className="breadcrumb">
        <Link to="/products">Products</Link> / {isEdit ? "Edit" : "New"}
      </p>
      <PageHeader title={isEdit ? "Edit product" : "New product"} />
      {!loaded ? (
        <p className="muted">Loading…</p>
      ) : (
        <form className="card form-card" onSubmit={handleSubmit} noValidate aria-label="product form">
          {formError && <Alert variant="error">{formError}</Alert>}
          <div className="form-grid">
            <TextField label="Name" value={form.name} onChange={update("name")} error={errors.name} autoFocus />
            <TextField
              label="SKU / Code"
              value={form.sku}
              onChange={update("sku")}
              error={errors.sku}
              hint="Unique product code, e.g. STL-ROD-10"
            />
            <SelectField label="Category" value={form.category_id} onChange={update("category_id")} error={errors.category_id}>
              <option value="">Select a category</option>
              {selectable(categories, form.category_id).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                  {c.is_active ? "" : " (inactive)"}
                </option>
              ))}
            </SelectField>
            <SelectField
              label="Unit of measure"
              value={form.unit_of_measure_id}
              onChange={update("unit_of_measure_id")}
              error={errors.unit_of_measure_id}
            >
              <option value="">Select a unit</option>
              {selectable(units, form.unit_of_measure_id).map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name} ({u.symbol})
                  {u.is_active ? "" : " (inactive)"}
                </option>
              ))}
            </SelectField>

            {!isEdit && (
              <>
                <TextField
                  label="Initial stock (optional)"
                  inputMode="decimal"
                  value={form.initial_stock}
                  onChange={update("initial_stock")}
                  error={errors.initial_stock}
                  hint="Quantity already on hand. Leave empty for none."
                />
                {hasInitialStock && (
                  <SelectField
                    label="Initial stock location"
                    value={form.initial_location_id}
                    onChange={update("initial_location_id")}
                    error={errors.initial_location_id}
                  >
                    <option value="">Select a location</option>
                    {locations.map((l) => (
                      <option key={l.id} value={l.id}>
                        {locationLabel(l)}
                      </option>
                    ))}
                  </SelectField>
                )}
              </>
            )}
          </div>
          {isEdit && (
            <CheckboxField
              label="Active"
              checked={form.is_active}
              onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
            />
          )}
          <div className="button-row">
            <Button type="submit" loading={saving} loadingText="Saving…">
              {isEdit ? "Save changes" : "Create product"}
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => navigate(isEdit ? `/products/${productId}` : "/products")}
              disabled={saving}
            >
              Cancel
            </Button>
          </div>
        </form>
      )}
    </section>
  );
}

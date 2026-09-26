import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { SelectField, TextField } from "../../components/ui/FormField";
import { PageHeader } from "../../components/ui/PageHeader";
import { onHandAt, operationApi } from "../../modules/inventory/api";
import { formatQuantity, type OperationConfig } from "../../modules/inventory/operations";
import { ALL, locationsApi, productsApi } from "../../modules/master-data/api";
import { locationLabel, type Location, type Product } from "../../modules/master-data/types";
import { requiredSelection, requiredText, validateQuantity } from "../../modules/master-data/validation";
import { ApiError } from "../../services/apiClient";

type Line = { key: number; product_id: string; quantity: string };

let nextKey = 1;
const newLine = (product_id = "", quantity = ""): Line => ({ key: nextKey++, product_id, quantity });

export function OperationFormPage({ config }: { config: OperationConfig }) {
  const params = useParams();
  const documentId = params.id ? Number(params.id) : null;
  const navigate = useNavigate();
  const api = operationApi(config.kind);

  const [header, setHeader] = useState<Record<string, string>>(() =>
    Object.fromEntries(config.headerFields.map((f) => [f.name, ""])),
  );
  const [lines, setLines] = useState<Line[]>([newLine()]);
  const [products, setProducts] = useState<Product[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [onHand, setOnHand] = useState<Map<number, number> | null>(null);
  const [reference, setReference] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [lineErrors, setLineErrors] = useState<Record<number, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const requests: Promise<unknown>[] = [
      productsApi.list({ limit: ALL, is_active: true }).then((page) => setProducts(page.items)),
      locationsApi
        .list({ limit: ALL, is_active: true })
        .then((page) => setLocations(page.items.filter((l) => l.warehouse.is_active))),
    ];
    if (documentId !== null) {
      requests.push(
        api.get(documentId).then((doc) => {
          setReference(doc.reference);
          const source = doc as unknown as Record<string, unknown>;
          setHeader(Object.fromEntries(config.headerFields.map((f) => [f.name, source[f.name] == null ? "" : String(source[f.name])])));
          setLines(doc.items.map((item) => newLine(String(item.product_id), String(item[config.quantityField] ?? ""))));
        }),
      );
    }
    Promise.all(requests)
      .then(() => setLoaded(true))
      .catch((err) => setLoadError(err instanceof ApiError ? err.message : "Unable to load the form."));
  }, [config.kind, documentId]);

  // Show current stock at the relevant location next to each line.
  const stockLocation = config.stockLocationField ? header[config.stockLocationField] : "";
  useEffect(() => {
    if (!stockLocation) {
      setOnHand(null);
      return;
    }
    let active = true;
    onHandAt(Number(stockLocation))
      .then((map) => active && setOnHand(map))
      .catch(() => active && setOnHand(null));
    return () => {
      active = false;
    };
  }, [stockLocation]);

  const isAdjustment = config.quantityField === "counted_quantity";
  const productById = new Map(products.map((p) => [p.id, p]));

  function updateLine(key: number, field: "product_id" | "quantity", value: string) {
    setLines((current) => current.map((line) => (line.key === key ? { ...line, [field]: value } : line)));
  }

  function validate(): boolean {
    const found: Record<string, string> = {};
    for (const field of config.headerFields) {
      const value = header[field.name] ?? "";
      if (field.type === "location") {
        const error = requiredSelection(value, "location");
        if (error) found[field.name] = error;
      } else if (field.type === "text" && field.required) {
        const error = requiredText(value, field.label, field.maxLength);
        if (error) found[field.name] = error;
      } else if (field.type === "text" && field.maxLength && value.trim().length > field.maxLength) {
        found[field.name] = `${field.label} must be at most ${field.maxLength} characters`;
      }
    }
    if (header.source_location_id && header.source_location_id === header.destination_location_id) {
      found.destination_location_id = "Source and destination must be different locations";
    }

    const foundLines: Record<number, string> = {};
    const seen = new Set<string>();
    for (const line of lines) {
      const productError = requiredSelection(line.product_id, "product");
      const quantityError = validateQuantity(line.quantity, config.quantityLabel);
      if (productError || quantityError) foundLines[line.key] = (productError ?? quantityError)!;
      else if (!isAdjustment && Number(line.quantity) <= 0) foundLines[line.key] = `${config.quantityLabel} must be greater than 0`;
      else if (seen.has(line.product_id)) foundLines[line.key] = "This product is already on another line";
      seen.add(line.product_id);
    }
    if (lines.length === 0) found.items = "Add at least one product";

    setErrors(found);
    setLineErrors(foundLines);
    return Object.keys(found).length === 0 && Object.keys(foundLines).length === 0;
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    if (!validate()) return;

    const body: Record<string, unknown> = {};
    for (const field of config.headerFields) {
      const value = (header[field.name] ?? "").trim();
      body[field.name] = field.type === "location" ? Number(value) : value === "" ? null : value;
    }
    body.items = lines.map((line) => ({ product_id: Number(line.product_id), [config.quantityField]: line.quantity.trim() }));

    setSaving(true);
    try {
      const saved = documentId !== null ? await api.update(documentId, body) : await api.create(body);
      navigate(`/${config.kind}/${saved.id}`, {
        state: { message: documentId !== null ? `${saved.reference} updated.` : `${saved.reference} created.` },
      });
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : `Unable to save the ${config.singular}.`);
      if (err instanceof ApiError) setErrors(err.fieldErrors);
      setSaving(false);
    }
  }

  if (loadError) return <Alert variant="error">{loadError}</Alert>;

  const title = documentId !== null ? `Edit ${reference ?? config.singular}` : `New ${config.singular}`;
  return (
    <section className="page page-wide">
      <p className="breadcrumb">
        <Link to={`/${config.kind}`}>{config.title}</Link> / {documentId !== null ? reference : "New"}
      </p>
      <PageHeader title={title} />
      {!loaded ? (
        <p className="muted">Loading…</p>
      ) : (
        <form className="card form-card" onSubmit={handleSubmit} noValidate aria-label={`${config.singular} form`}>
          {formError && <Alert variant="error">{formError}</Alert>}
          <div className="form-grid">
            {config.headerFields.map((field) =>
              field.type === "location" ? (
                <SelectField
                  key={field.name}
                  label={field.label}
                  value={header[field.name]}
                  onChange={(e) => setHeader((h) => ({ ...h, [field.name]: e.target.value }))}
                  error={errors[field.name]}
                >
                  <option value="">Select a location</option>
                  {locations.map((l) => (
                    <option key={l.id} value={l.id}>
                      {locationLabel(l)}
                    </option>
                  ))}
                </SelectField>
              ) : (
                <TextField
                  key={field.name}
                  label={field.label}
                  type={field.type === "date" ? "date" : "text"}
                  value={header[field.name]}
                  onChange={(e) => setHeader((h) => ({ ...h, [field.name]: e.target.value }))}
                  error={errors[field.name]}
                  hint={field.type === "text" ? field.hint : undefined}
                />
              ),
            )}
          </div>

          <h2>Products</h2>
          {errors.items && <Alert variant="error">{errors.items}</Alert>}
          <div className="table-wrap">
            <table className="table lines-table">
              <thead>
                <tr>
                  <th>Product</th>
                  {onHand && <th className="num">{isAdjustment ? "Recorded" : "Available"}</th>}
                  <th className="num">{config.quantityLabel}</th>
                  {isAdjustment && onHand && <th className="num">Difference</th>}
                  <th />
                </tr>
              </thead>
              <tbody>
                {lines.map((line, index) => {
                  const product = productById.get(Number(line.product_id));
                  const unit = product?.unit_of_measure.symbol;
                  const available = line.product_id && onHand ? onHand.get(Number(line.product_id)) ?? 0 : null;
                  const quantity = Number(line.quantity);
                  const hasQuantity = line.quantity.trim() !== "" && !Number.isNaN(quantity);
                  const short = !isAdjustment && available !== null && hasQuantity && quantity > available;
                  return (
                    <tr key={line.key}>
                      <td>
                        <select
                          aria-label={`Product for line ${index + 1}`}
                          value={line.product_id}
                          onChange={(e) => updateLine(line.key, "product_id", e.target.value)}
                        >
                          <option value="">Select a product</option>
                          {products.map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.name} ({p.sku})
                            </option>
                          ))}
                        </select>
                        {lineErrors[line.key] && <p className="field-error">{lineErrors[line.key]}</p>}
                      </td>
                      {onHand && <td className="num">{available === null ? "—" : formatQuantity(available, unit)}</td>}
                      <td className="num">
                        <input
                          aria-label={`${config.quantityLabel} for line ${index + 1}`}
                          inputMode="decimal"
                          value={line.quantity}
                          onChange={(e) => updateLine(line.key, "quantity", e.target.value)}
                          className="qty-input"
                        />
                        {short && <p className="field-hint warning">Only {formatQuantity(available, unit)} available</p>}
                      </td>
                      {isAdjustment && onHand && (
                        <td className="num">
                          {available !== null && hasQuantity ? formatSigned(quantity - available, unit) : "—"}
                        </td>
                      )}
                      <td className="actions-col">
                        <button
                          type="button"
                          className="link-button danger"
                          onClick={() => setLines((current) => current.filter((l) => l.key !== line.key))}
                          disabled={lines.length === 1}
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <Button type="button" variant="link" onClick={() => setLines((current) => [...current, newLine()])}>
            + Add product
          </Button>

          <div className="button-row">
            <Button type="submit" loading={saving} loadingText="Saving…">
              {documentId !== null ? "Save changes" : `Create ${config.singular}`}
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => navigate(documentId !== null ? `/${config.kind}/${documentId}` : `/${config.kind}`)}
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

function formatSigned(value: number, unit?: string) {
  const text = formatQuantity(Math.abs(value), unit);
  return value > 0 ? `+${text}` : value < 0 ? `−${text}` : text;
}

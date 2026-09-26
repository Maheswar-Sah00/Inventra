import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { CheckboxField } from "../../components/ui/CheckboxField";
import { SelectField, TextField } from "../../components/ui/FormField";
import { Pagination } from "../../components/ui/Pagination";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { ApiError } from "../../services/apiClient";
import { useAuth } from "../auth";
import { ALL, locationsApi, warehousesApi } from "./api";
import { useDebouncedValue, usePagedList } from "./hooks";
import { StatusFilterSelect, statusParam, type StatusFilter } from "./SimpleEntityPage";
import type { Location, Warehouse } from "./types";
import { requiredSelection, requiredText, validateCode } from "./validation";

type Props = {
  /** Show and create locations of this warehouse only. Omit to manage locations across warehouses. */
  warehouseId?: number;
};

export function LocationsManager({ warehouseId }: Props) {
  const { hasRole } = useAuth();
  const canManage = hasRole("INVENTORY_MANAGER");

  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [warehouseFilter, setWarehouseFilter] = useState<string>("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StatusFilter>("active");
  const [offset, setOffset] = useState(0);
  const q = useDebouncedValue(search.trim());
  const scopedWarehouse = warehouseId ?? (warehouseFilter ? Number(warehouseFilter) : undefined);

  const { data, loading, error, reload } = usePagedList<Location>(locationsApi.list, {
    warehouse_id: scopedWarehouse,
    q,
    is_active: statusParam(status),
    limit: 20,
    offset,
  });

  useEffect(() => {
    if (warehouseId !== undefined) return;
    warehousesApi
      .list({ limit: ALL })
      .then((page) => setWarehouses(page.items))
      .catch(() => setWarehouses([]));
  }, [warehouseId]);

  const [editing, setEditing] = useState<Location | "new" | null>(null);
  const [form, setForm] = useState({ warehouse_id: "", name: "", code: "", is_active: true });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function openForm(item: Location | "new") {
    setForm(
      item === "new"
        ? { warehouse_id: String(scopedWarehouse ?? ""), name: "", code: "", is_active: true }
        : { warehouse_id: String(item.warehouse_id), name: item.name, code: item.code, is_active: item.is_active },
    );
    setErrors({});
    setFormError(null);
    setNotice(null);
    setEditing(item);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const found: Record<string, string> = {};
    const warehouseError = editing === "new" ? requiredSelection(form.warehouse_id, "warehouse") : null;
    const nameError = requiredText(form.name, "Name");
    const codeError = validateCode(form.code);
    if (warehouseError) found.warehouse_id = warehouseError;
    if (nameError) found.name = nameError;
    if (codeError) found.code = codeError;
    setErrors(found);
    setFormError(null);
    if (Object.keys(found).length || editing === null) return;

    setSaving(true);
    try {
      const common = { name: form.name.trim(), code: form.code.trim(), is_active: form.is_active };
      if (editing === "new") await locationsApi.create({ ...common, warehouse_id: Number(form.warehouse_id) });
      else await locationsApi.update(editing.id, common);
      setNotice(editing === "new" ? "Location created." : "Location updated.");
      setEditing(null);
      reload();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Unable to save the location.");
      if (err instanceof ApiError) setErrors(err.fieldErrors);
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(location: Location) {
    setNotice(null);
    setFormError(null);
    try {
      await locationsApi.update(location.id, { is_active: !location.is_active });
      setNotice(`Location ${location.is_active ? "deactivated" : "activated"}.`);
      reload();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Unable to update the location.");
    }
  }

  const showWarehouseColumn = warehouseId === undefined;

  return (
    <div className="locations-manager">
      <div className="section-header">
        <h2>Locations</h2>
        {canManage && editing === null && (
          <Button type="button" onClick={() => openForm("new")}>
            New location
          </Button>
        )}
      </div>

      {notice && <Alert variant="success">{notice}</Alert>}
      {formError && editing === null && <Alert variant="error">{formError}</Alert>}

      {editing !== null && (
        <form className="card form-card" onSubmit={handleSubmit} noValidate aria-label="location form">
          <h3>{editing === "new" ? "New location" : "Edit location"}</h3>
          {formError && <Alert variant="error">{formError}</Alert>}
          <div className="form-grid">
            {editing === "new" && warehouseId === undefined && (
              <SelectField
                label="Warehouse"
                value={form.warehouse_id}
                onChange={(e) => setForm((f) => ({ ...f, warehouse_id: e.target.value }))}
                error={errors.warehouse_id}
              >
                <option value="">Select a warehouse</option>
                {warehouses
                  .filter((w) => w.is_active)
                  .map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.name} ({w.code})
                    </option>
                  ))}
              </SelectField>
            )}
            <TextField
              label="Name"
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              error={errors.name}
              hint="e.g. Rack A, Production Floor"
              autoFocus
            />
            <TextField
              label="Code"
              value={form.code}
              onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))}
              error={errors.code}
              hint="Unique within the warehouse, e.g. RACK-A"
            />
          </div>
          <CheckboxField
            label="Active"
            checked={form.is_active}
            onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
          />
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
        {showWarehouseColumn && (
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
        )}
        <TextField
          label="Search"
          type="search"
          placeholder="Name or code"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setOffset(0);
          }}
        />
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
              {showWarehouseColumn && <th>Warehouse</th>}
              <th>Name</th>
              <th>Code</th>
              <th>Status</th>
              {canManage && <th className="actions-col">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {data?.items.map((location) => (
              <tr key={location.id}>
                {showWarehouseColumn && (
                  <td>
                    <Link to={`/warehouses/${location.warehouse_id}`}>{location.warehouse.name}</Link>
                  </td>
                )}
                <td>{location.name}</td>
                <td className="mono">{location.code}</td>
                <td>
                  <StatusBadge active={location.is_active} />
                </td>
                {canManage && (
                  <td className="actions-col">
                    <button type="button" className="link-button" onClick={() => openForm(location)}>
                      Edit
                    </button>
                    <button type="button" className="link-button" onClick={() => toggleActive(location)}>
                      {location.is_active ? "Deactivate" : "Activate"}
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        {loading && <p className="muted table-message">Loading…</p>}
        {!loading && data?.items.length === 0 && <p className="muted table-message">No locations found.</p>}
      </div>
      {data && <Pagination total={data.total} limit={data.limit} offset={data.offset} onChange={setOffset} />}
    </div>
  );
}

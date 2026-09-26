import { useState, type FormEvent, type ReactNode } from "react";

import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { CheckboxField } from "../../components/ui/CheckboxField";
import { SelectField, TextField } from "../../components/ui/FormField";
import { PageHeader } from "../../components/ui/PageHeader";
import { Pagination } from "../../components/ui/Pagination";
import { StatusBadge } from "../../components/ui/StatusBadge";
import { ApiError } from "../../services/apiClient";
import { useAuth } from "../auth";
import { useDebouncedValue, usePagedList } from "./hooks";
import type { ListParams, Page } from "./types";
import { requiredText, validateCode } from "./validation";

export type StatusFilter = "active" | "inactive" | "all";

export function statusParam(filter: StatusFilter): boolean | undefined {
  return filter === "all" ? undefined : filter === "active";
}

export function StatusFilterSelect({ value, onChange }: { value: StatusFilter; onChange: (value: StatusFilter) => void }) {
  return (
    <SelectField label="Status" value={value} onChange={(e) => onChange(e.target.value as StatusFilter)}>
      <option value="active">Active</option>
      <option value="inactive">Inactive</option>
      <option value="all">All</option>
    </SelectField>
  );
}

export type FieldSpec = {
  name: string;
  label: string;
  /** "code" fields are upper-cased by the API and use code validation. */
  kind?: "text" | "code";
  required?: boolean;
  maxLength?: number;
  hint?: string;
};

export type ColumnSpec<T> = { header: string; render: (item: T) => ReactNode };

type Entity = { id: number; is_active: boolean };
type FormValues = Record<string, string>;

type Api<T> = {
  list: (params: ListParams, signal?: AbortSignal) => Promise<Page<T>>;
  create: (data: never) => Promise<T>;
  update: (id: number, data: never) => Promise<T>;
};

type Props<T extends Entity> = {
  title: string;
  singular: string;
  description?: string;
  api: Api<T>;
  fields: FieldSpec[];
  columns: ColumnSpec<T>[];
  searchPlaceholder: string;
  pageSize?: number;
};

const PAGE_SIZE = 20;

/**
 * List + search + status filter + create/edit form for simple master-data records
 * (categories, units of measure, warehouses).
 */
export function SimpleEntityPage<T extends Entity>({
  title,
  singular,
  description,
  api,
  fields,
  columns,
  searchPlaceholder,
  pageSize = PAGE_SIZE,
}: Props<T>) {
  const { hasRole } = useAuth();
  const canManage = hasRole("INVENTORY_MANAGER");

  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<StatusFilter>("active");
  const [offset, setOffset] = useState(0);
  const q = useDebouncedValue(search.trim());
  const { data, loading, error, reload } = usePagedList<T>(api.list, {
    q,
    is_active: statusParam(status),
    limit: pageSize,
    offset,
  });

  const [editing, setEditing] = useState<T | "new" | null>(null);
  const [values, setValues] = useState<FormValues>({});
  const [isActive, setIsActive] = useState(true);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function openForm(item: T | "new") {
    const source = item === "new" ? {} : (item as unknown as Record<string, unknown>);
    setValues(Object.fromEntries(fields.map((f) => [f.name, String(source[f.name] ?? "")])));
    setIsActive(item === "new" ? true : item.is_active);
    setErrors({});
    setFormError(null);
    setNotice(null);
    setEditing(item);
  }

  function validate(): Record<string, string> {
    const found: Record<string, string> = {};
    for (const field of fields) {
      const value = values[field.name] ?? "";
      let message: string | null = null;
      if (field.kind === "code") message = validateCode(value, field.label, field.maxLength);
      else if (field.required) message = requiredText(value, field.label, field.maxLength);
      else if (field.maxLength && value.trim().length > field.maxLength)
        message = `${field.label} must be at most ${field.maxLength} characters`;
      if (message) found[field.name] = message;
    }
    return found;
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const found = validate();
    setErrors(found);
    setFormError(null);
    if (Object.keys(found).length || editing === null) return;

    const payload: Record<string, unknown> = { is_active: isActive };
    for (const field of fields) {
      const value = (values[field.name] ?? "").trim();
      payload[field.name] = value === "" && !field.required && field.kind !== "code" ? null : value;
    }

    setSaving(true);
    try {
      if (editing === "new") await api.create(payload as never);
      else await api.update(editing.id, payload as never);
      setNotice(editing === "new" ? `${capitalize(singular)} created.` : `${capitalize(singular)} updated.`);
      setEditing(null);
      reload();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : `Unable to save the ${singular}.`);
      if (err instanceof ApiError) setErrors(err.fieldErrors);
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(item: T) {
    setNotice(null);
    setFormError(null);
    try {
      await api.update(item.id, { is_active: !item.is_active } as never);
      setNotice(`${capitalize(singular)} ${item.is_active ? "deactivated" : "activated"}.`);
      reload();
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : `Unable to update the ${singular}.`);
    }
  }

  return (
    <section className="page page-wide">
      <PageHeader
        title={title}
        description={description}
        actions={
          canManage && editing === null ? (
            <Button type="button" onClick={() => openForm("new")}>
              New {singular}
            </Button>
          ) : undefined
        }
      />

      {notice && <Alert variant="success">{notice}</Alert>}
      {formError && editing === null && <Alert variant="error">{formError}</Alert>}

      {editing !== null && (
        <form className="card form-card" onSubmit={handleSubmit} noValidate aria-label={`${singular} form`}>
          <h2>{editing === "new" ? `New ${singular}` : `Edit ${singular}`}</h2>
          {formError && <Alert variant="error">{formError}</Alert>}
          <div className="form-grid">
            {fields.map((field, index) => (
              <TextField
                key={field.name}
                label={field.label}
                value={values[field.name] ?? ""}
                onChange={(e) => setValues((v) => ({ ...v, [field.name]: e.target.value }))}
                error={errors[field.name]}
                hint={field.hint}
                autoFocus={index === 0}
              />
            ))}
          </div>
          <CheckboxField label="Active" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} />
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
        <TextField label="Search" type="search" placeholder={searchPlaceholder} value={search} onChange={(e) => {
          setSearch(e.target.value);
          setOffset(0);
        }} />
        <StatusFilterSelect value={status} onChange={(value) => { setStatus(value); setOffset(0); }} />
      </div>

      {error && <Alert variant="error">{error}</Alert>}
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column.header}>{column.header}</th>
              ))}
              <th>Status</th>
              {canManage && <th className="actions-col">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {data?.items.map((item) => (
              <tr key={item.id}>
                {columns.map((column) => (
                  <td key={column.header}>{column.render(item)}</td>
                ))}
                <td>
                  <StatusBadge active={item.is_active} />
                </td>
                {canManage && (
                  <td className="actions-col">
                    <button type="button" className="link-button" onClick={() => openForm(item)}>
                      Edit
                    </button>
                    <button type="button" className="link-button" onClick={() => toggleActive(item)}>
                      {item.is_active ? "Deactivate" : "Activate"}
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        {loading && <p className="muted table-message">Loading…</p>}
        {!loading && data?.items.length === 0 && <p className="muted table-message">No {title.toLowerCase()} found.</p>}
      </div>
      {data && <Pagination total={data.total} limit={data.limit} offset={data.offset} onChange={setOffset} />}
    </section>
  );
}

function capitalize(text: string) {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

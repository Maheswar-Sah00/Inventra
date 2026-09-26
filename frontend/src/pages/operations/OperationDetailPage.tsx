import { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { PageHeader } from "../../components/ui/PageHeader";
import { operationApi, stockApi } from "../../modules/inventory/api";
import { DocumentStatusBadge } from "../../modules/inventory/DocumentStatusBadge";
import { formatDateTime, formatQuantity, type OperationConfig } from "../../modules/inventory/operations";
import {
  OPEN_STATUSES,
  type DocumentAction,
  type InventoryDocument,
  type StockMovement,
} from "../../modules/inventory/types";
import { locationLabel } from "../../modules/master-data/types";
import { ApiError } from "../../services/apiClient";

type ActionButton = { action: DocumentAction; label: string; primary?: boolean };

function availableActions(config: OperationConfig, doc: InventoryDocument): ActionButton[] {
  if (!OPEN_STATUSES.includes(doc.status)) return [];
  const actions: ActionButton[] = [];
  if (doc.status === "DRAFT" || doc.status === "WAITING") actions.push({ action: "confirm", label: config.confirmLabel });
  if (config.pickPack) {
    if (doc.status === "READY" && !doc.picked_at) actions.push({ action: "pick", label: "Pick", primary: true });
    if (doc.status === "READY" && doc.picked_at && !doc.packed_at) actions.push({ action: "pack", label: "Pack", primary: true });
    if (doc.status === "READY" && doc.packed_at) actions.push({ action: "validate", label: "Validate", primary: true });
  } else {
    actions.push({ action: "validate", label: "Validate", primary: true });
  }
  actions.push({ action: "cancel", label: "Cancel" });
  return actions;
}

const ACTION_MESSAGES: Record<DocumentAction, string> = {
  confirm: "Availability checked.",
  pick: "Items picked.",
  pack: "Items packed.",
  validate: "Validated. Stock has been updated.",
  cancel: "Canceled.",
};

export function OperationDetailPage({ config }: { config: OperationConfig }) {
  const id = Number(useParams().id);
  const navigate = useNavigate();
  const location = useLocation();
  const api = operationApi(config.kind);

  const [doc, setDoc] = useState<InventoryDocument | null>(null);
  const [movements, setMovements] = useState<StockMovement[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>((location.state as { message?: string } | null)?.message ?? null);
  const [busy, setBusy] = useState<DocumentAction | null>(null);

  const loadMovements = useCallback(
    (document: InventoryDocument) => {
      if (document.status !== "DONE") return setMovements([]);
      stockApi
        .movements({ reference_type: config.movementReference, reference_id: document.id, limit: 200 })
        .then((page) => setMovements(page.items))
        .catch(() => setMovements([]));
    },
    [config.movementReference],
  );

  useEffect(() => {
    const controller = new AbortController();
    api
      .get(id, controller.signal)
      .then((document) => {
        setDoc(document);
        loadMovements(document);
      })
      .catch((err: Error) => {
        if (err.name !== "AbortError") setLoadError(err instanceof ApiError ? err.message : "Unable to load.");
      });
    return () => controller.abort();
  }, [config.kind, id]);

  async function run(action: DocumentAction) {
    if (!doc) return;
    if (action === "cancel" && !window.confirm(`Cancel ${doc.reference}? This cannot be undone.`)) return;
    setBusy(action);
    setActionError(null);
    setNotice(null);
    try {
      const updated = await api.action(doc.id, action);
      setDoc(updated);
      loadMovements(updated);
      setNotice(
        action === "confirm" && updated.status === "WAITING"
          ? "Not enough stock yet — the order is waiting. Check again when stock arrives."
          : ACTION_MESSAGES[action],
      );
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "The action failed. Please try again.");
    } finally {
      setBusy(null);
    }
  }

  if (loadError) return <Alert variant="error">{loadError}</Alert>;
  if (!doc) return <p className="muted">Loading…</p>;

  const open = OPEN_STATUSES.includes(doc.status);
  const isAdjustment = config.quantityField === "counted_quantity";
  const outgoing = Boolean(config.stockLocationField) && !isAdjustment;

  return (
    <section className="page page-wide">
      <p className="breadcrumb">
        <Link to={`/${config.kind}`}>{config.title}</Link> / {doc.reference}
      </p>
      <PageHeader
        title={doc.reference}
        actions={
          <>
            {open && (
              <Button type="button" variant="secondary" onClick={() => navigate(`/${config.kind}/${doc.id}/edit`)}>
                Edit
              </Button>
            )}
            {availableActions(config, doc).map(({ action, label, primary }) => (
              <Button
                key={action}
                type="button"
                variant={primary ? "primary" : "secondary"}
                onClick={() => run(action)}
                loading={busy === action}
                disabled={busy !== null}
              >
                {label}
              </Button>
            ))}
          </>
        }
      />
      {notice && <Alert variant={doc.status === "WAITING" ? "info" : "success"}>{notice}</Alert>}
      {actionError && <Alert variant="error">{actionError}</Alert>}

      <div className="card">
        <dl className="details">
          <dt>Status</dt>
          <dd>
            <DocumentStatusBadge status={doc.status} />
            {config.pickPack && doc.status === "READY" && (
              <span className="muted small"> · {doc.packed_at ? "Packed" : doc.picked_at ? "Picked" : "Not picked yet"}</span>
            )}
          </dd>
          {doc.supplier_name !== undefined && (
            <>
              <dt>Supplier</dt>
              <dd>
                {doc.supplier_name}
                {doc.supplier_reference ? ` (${doc.supplier_reference})` : ""}
              </dd>
            </>
          )}
          {doc.customer_name !== undefined && (
            <>
              <dt>Customer</dt>
              <dd>{doc.customer_name ?? "—"}</dd>
            </>
          )}
          {doc.source_location && (
            <>
              <dt>From</dt>
              <dd>{locationLabel(doc.source_location)}</dd>
            </>
          )}
          {doc.destination_location && (
            <>
              <dt>To</dt>
              <dd>{locationLabel(doc.destination_location)}</dd>
            </>
          )}
          {doc.location && (
            <>
              <dt>Location</dt>
              <dd>{locationLabel(doc.location)}</dd>
            </>
          )}
          {doc.reason !== undefined && (
            <>
              <dt>Reason</dt>
              <dd>{doc.reason}</dd>
            </>
          )}
          {doc.scheduled_date !== undefined && config.kind !== "adjustments" && (
            <>
              <dt>Scheduled</dt>
              <dd>{doc.scheduled_date ?? "—"}</dd>
            </>
          )}
          {doc.notes && (
            <>
              <dt>Notes</dt>
              <dd>{doc.notes}</dd>
            </>
          )}
          <dt>Created</dt>
          <dd>
            {formatDateTime(doc.created_at)} by {doc.created_by.name}
          </dd>
          {doc.picked_at && (
            <>
              <dt>Picked</dt>
              <dd>
                {formatDateTime(doc.picked_at)} by {doc.picked_by?.name}
              </dd>
            </>
          )}
          {doc.packed_at && (
            <>
              <dt>Packed</dt>
              <dd>
                {formatDateTime(doc.packed_at)} by {doc.packed_by?.name}
              </dd>
            </>
          )}
          {doc.validated_at && (
            <>
              <dt>Validated</dt>
              <dd>
                {formatDateTime(doc.validated_at)} by {doc.validated_by?.name}
              </dd>
            </>
          )}
          {doc.canceled_at && (
            <>
              <dt>Canceled</dt>
              <dd>{formatDateTime(doc.canceled_at)}</dd>
            </>
          )}
        </dl>
      </div>

      <h2 className="section-title">Products</h2>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Product</th>
              <th>SKU</th>
              {isAdjustment ? (
                <>
                  <th className="num">Recorded</th>
                  <th className="num">Counted</th>
                  <th className="num">Difference</th>
                </>
              ) : (
                <>
                  <th className="num">Quantity</th>
                  {outgoing && open && <th className="num">Available</th>}
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {doc.items.map((item) => {
              const unit = item.product.unit_of_measure.symbol;
              const recorded = open ? item.current_quantity : item.recorded_quantity;
              const difference =
                open && recorded !== null && recorded !== undefined && item.counted_quantity !== undefined
                  ? item.counted_quantity - recorded
                  : item.difference;
              const short =
                outgoing && open && item.available_quantity != null && (item.quantity ?? 0) > item.available_quantity;
              return (
                <tr key={item.id}>
                  <td>
                    <Link to={`/products/${item.product_id}`}>{item.product.name}</Link>
                  </td>
                  <td className="mono">{item.product.sku}</td>
                  {isAdjustment ? (
                    <>
                      <td className="num">{formatQuantity(recorded, unit)}</td>
                      <td className="num">{formatQuantity(item.counted_quantity, unit)}</td>
                      <td className="num">{difference == null ? "—" : signed(difference, unit)}</td>
                    </>
                  ) : (
                    <>
                      <td className="num">{formatQuantity(item.quantity, unit)}</td>
                      {outgoing && open && (
                        <td className={`num${short ? " text-danger" : ""}`}>
                          {formatQuantity(item.available_quantity, unit)}
                          {short && " (not enough)"}
                        </td>
                      )}
                    </>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {movements.length > 0 && (
        <>
          <h2 className="section-title">Stock movements</h2>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>From</th>
                  <th>To</th>
                  <th className="num">Quantity</th>
                  <th>By</th>
                </tr>
              </thead>
              <tbody>
                {movements.map((m) => (
                  <tr key={m.id}>
                    <td>{m.product.name}</td>
                    <td>{m.source_location ? locationLabel(m.source_location) : "—"}</td>
                    <td>{m.destination_location ? locationLabel(m.destination_location) : "—"}</td>
                    <td className="num">{signed(m.quantity, m.product.unit_of_measure.symbol)}</td>
                    <td>{m.performed_by.name}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

function signed(value: number, unit?: string) {
  const text = formatQuantity(Math.abs(value), unit);
  return value > 0 ? `+${text}` : value < 0 ? `−${text}` : text;
}

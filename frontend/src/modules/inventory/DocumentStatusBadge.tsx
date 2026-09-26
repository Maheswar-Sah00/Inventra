import type { DocumentStatus } from "./types";
import { STATUS_LABELS } from "./operations";

export function DocumentStatusBadge({ status }: { status: DocumentStatus }) {
  return <span className={`badge status-${status.toLowerCase()}`}>{STATUS_LABELS[status] ?? status}</span>;
}

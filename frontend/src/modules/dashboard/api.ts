import { apiRequest } from "../../services/apiClient";
import { buildQuery, type QueryParams } from "../inventory/api";
import type { Page } from "../master-data/types";
import type { AvailabilityRow, DashboardSummary } from "./types";

export const dashboardApi = {
  summary: (params: QueryParams, signal?: AbortSignal) =>
    apiRequest<DashboardSummary>(`/dashboard/summary${buildQuery(params)}`, { signal }),
  availability: (params: QueryParams, signal?: AbortSignal) =>
    apiRequest<Page<AvailabilityRow>>(`/stock-availability${buildQuery(params)}`, { signal }),
};

/** Stock availability `status` values travel comma-joined in the URL and are sent as repeated params. */
export function splitList(value: string | number | boolean | null | undefined): string[] | undefined {
  return value ? String(value).split(",").filter(Boolean) : undefined;
}

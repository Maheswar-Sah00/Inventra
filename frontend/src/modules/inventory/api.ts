import { apiRequest } from "../../services/apiClient";
import type { Page } from "../master-data/types";
import type {
  DocumentAction,
  InventoryDocument,
  OperationKind,
  ProductStock,
  StockMovement,
  StockPosition,
} from "./types";

export type QueryValue = string | number | boolean | null | undefined | (string | number)[];
export type QueryParams = Record<string, QueryValue>;

/** Builds a query string; arrays repeat the key (?status=DRAFT&status=READY); empty values are skipped. */
export function buildQuery(params: QueryParams = {}): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    const values = Array.isArray(value) ? value : [value];
    for (const item of values) {
      if (item !== undefined && item !== null && item !== "") query.append(key, String(item));
    }
  }
  const text = query.toString();
  return text ? `?${text}` : "";
}

export function operationApi(kind: OperationKind) {
  const base = `/${kind}`;
  return {
    list: (params?: QueryParams, signal?: AbortSignal) =>
      apiRequest<Page<InventoryDocument>>(`${base}${buildQuery(params)}`, { signal }),
    get: (id: number, signal?: AbortSignal) => apiRequest<InventoryDocument>(`${base}/${id}`, { signal }),
    create: (body: Record<string, unknown>) => apiRequest<InventoryDocument>(base, { method: "POST", body }),
    update: (id: number, body: Record<string, unknown>) =>
      apiRequest<InventoryDocument>(`${base}/${id}`, { method: "PATCH", body }),
    action: (id: number, action: DocumentAction) =>
      apiRequest<InventoryDocument>(`${base}/${id}/${action}`, { method: "POST" }),
  };
}

export const stockApi = {
  list: (params?: QueryParams, signal?: AbortSignal) =>
    apiRequest<Page<StockPosition>>(`/stock${buildQuery(params)}`, { signal }),
  product: (productId: number, signal?: AbortSignal) =>
    apiRequest<ProductStock>(`/stock/products/${productId}`, { signal }),
  movements: (params?: QueryParams, signal?: AbortSignal) =>
    apiRequest<Page<StockMovement>>(`/stock-movements${buildQuery(params)}`, { signal }),
};

/** On-hand quantity by product at one location (for availability hints in forms). */
export async function onHandAt(locationId: number): Promise<Map<number, number>> {
  const page = await stockApi.list({ location_id: locationId, limit: 500 });
  return new Map(page.items.map((row) => [row.product_id, row.quantity]));
}

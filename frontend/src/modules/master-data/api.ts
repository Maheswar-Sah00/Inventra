import { apiRequest } from "../../services/apiClient";
import type {
  Category,
  ListParams,
  Location,
  Page,
  Product,
  ProductCreate,
  ProductUpdate,
  ReorderRule,
  ReorderRuleCreate,
  ReorderRuleUpdate,
  Unit,
  Warehouse,
} from "./types";

/** Builds "?a=1&b=x", skipping empty values. */
export function toQuery(params: ListParams = {}): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") query.set(key, String(value));
  }
  const text = query.toString();
  return text ? `?${text}` : "";
}

function resource<T, TCreate, TUpdate>(path: string) {
  return {
    list: (params?: ListParams, signal?: AbortSignal) => apiRequest<Page<T>>(`${path}${toQuery(params)}`, { signal }),
    get: (id: number, signal?: AbortSignal) => apiRequest<T>(`${path}/${id}`, { signal }),
    create: (data: TCreate) => apiRequest<T>(path, { method: "POST", body: data }),
    update: (id: number, data: TUpdate) => apiRequest<T>(`${path}/${id}`, { method: "PATCH", body: data }),
    remove: (id: number) => apiRequest<null>(`${path}/${id}`, { method: "DELETE" }),
  };
}

type Editable<T, K extends keyof T> = Pick<T, K>;

export type CategoryInput = Editable<Category, "name" | "description" | "is_active">;
export type UnitInput = Editable<Unit, "name" | "symbol" | "is_active">;
export type WarehouseInput = Editable<Warehouse, "name" | "code" | "address" | "is_active">;
export type LocationCreate = Editable<Location, "warehouse_id" | "name" | "code" | "is_active">;
export type LocationUpdate = Partial<Editable<Location, "name" | "code" | "is_active">>;

export const categoriesApi = resource<Category, CategoryInput, Partial<CategoryInput>>("/categories");
export const unitsApi = resource<Unit, UnitInput, Partial<UnitInput>>("/units");
export const warehousesApi = resource<Warehouse, WarehouseInput, Partial<WarehouseInput>>("/warehouses");
export const locationsApi = resource<Location, LocationCreate, LocationUpdate>("/locations");
export const productsApi = resource<Product, ProductCreate, ProductUpdate>("/products");
export const reorderRulesApi = resource<ReorderRule, ReorderRuleCreate, ReorderRuleUpdate>("/reorder-rules");

/** Largest page the API allows; used to fill dropdowns. */
export const ALL = 500;

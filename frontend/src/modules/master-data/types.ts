export type Page<T> = { items: T[]; total: number; limit: number; offset: number };

type Timestamps = { created_at: string; updated_at: string };

export type CategoryRef = { id: number; name: string };
export type UnitRef = { id: number; name: string; symbol: string };
export type WarehouseRef = { id: number; name: string; code: string; is_active: boolean };
export type LocationRef = { id: number; name: string; code: string; is_active: boolean; warehouse: WarehouseRef };
export type ProductRef = { id: number; name: string; sku: string; is_active: boolean };

export type Category = Timestamps & { id: number; name: string; description: string | null; is_active: boolean };

export type Unit = Timestamps & { id: number; name: string; symbol: string; is_active: boolean };

export type Warehouse = Timestamps & {
  id: number;
  name: string;
  code: string;
  address: string | null;
  is_active: boolean;
};

export type Location = Timestamps & {
  id: number;
  warehouse_id: number;
  warehouse: WarehouseRef;
  name: string;
  code: string;
  is_active: boolean;
};

export type Product = Timestamps & {
  id: number;
  name: string;
  sku: string;
  category_id: number;
  category: CategoryRef;
  unit_of_measure_id: number;
  unit_of_measure: UnitRef;
  initial_stock: number;
  initial_location_id: number | null;
  initial_location: LocationRef | null;
  is_active: boolean;
};

export type ReorderRule = Timestamps & {
  id: number;
  product_id: number;
  product: ProductRef;
  location_id: number;
  location: LocationRef;
  minimum_quantity: number;
  target_quantity: number;
  is_active: boolean;
};

/** Quantities are sent as the decimal string the user typed, so no precision is lost. */
export type ProductCreate = {
  name: string;
  sku: string;
  category_id: number;
  unit_of_measure_id: number;
  initial_stock?: string;
  initial_location_id?: number | null;
};
export type ProductUpdate = Partial<Pick<Product, "name" | "sku" | "category_id" | "unit_of_measure_id" | "is_active">>;

export type ReorderRuleCreate = {
  product_id: number;
  location_id: number;
  minimum_quantity: string;
  target_quantity: string;
  is_active?: boolean;
};
export type ReorderRuleUpdate = { minimum_quantity?: string; target_quantity?: string; is_active?: boolean };

export type ListParams = Record<string, string | number | boolean | null | undefined>;

/** Label for a location, e.g. "WH-MAIN / Rack A". */
export function locationLabel(location: LocationRef | Location) {
  return `${location.warehouse.code} / ${location.name}`;
}

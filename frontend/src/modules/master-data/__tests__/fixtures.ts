import type { Category, Location, Product, ReorderRule, Unit, Warehouse } from "../types";

const stamps = { created_at: "2026-09-26T05:00:00Z", updated_at: "2026-09-26T05:00:00Z" };

export const rawMaterials: Category = { id: 1, name: "Raw Materials", description: null, is_active: true, ...stamps };
export const finishedGoods: Category = { id: 2, name: "Finished Goods", description: null, is_active: true, ...stamps };
export const kilogram: Unit = { id: 1, name: "Kilogram", symbol: "kg", is_active: true, ...stamps };
export const mainWarehouse: Warehouse = {
  id: 1,
  name: "Main Warehouse",
  code: "WH-MAIN",
  address: null,
  is_active: true,
  ...stamps,
};
const warehouseRef = { id: 1, name: "Main Warehouse", code: "WH-MAIN", is_active: true };
export const rackA: Location = { id: 10, warehouse_id: 1, warehouse: warehouseRef, name: "Rack A", code: "RACK-A", is_active: true, ...stamps };

export const steelRods: Product = {
  id: 100,
  name: "Steel Rods",
  sku: "STL-ROD",
  category_id: 1,
  category: { id: 1, name: "Raw Materials" },
  unit_of_measure_id: 1,
  unit_of_measure: { id: 1, name: "Kilogram", symbol: "kg" },
  initial_stock: 0,
  initial_location_id: null,
  initial_location: null,
  is_active: true,
  ...stamps,
};

export const steelRule: ReorderRule = {
  id: 7,
  product_id: 100,
  product: { id: 100, name: "Steel Rods", sku: "STL-ROD", is_active: true },
  location_id: 10,
  location: { id: 10, name: "Rack A", code: "RACK-A", is_active: true, warehouse: warehouseRef },
  minimum_quantity: 10,
  target_quantity: 50,
  is_active: true,
  ...stamps,
};

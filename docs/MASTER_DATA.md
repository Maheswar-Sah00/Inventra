# Products & Warehouse Master Data Module

Owner: Gautam. This module holds the reference data the inventory system runs on: **products,
categories, units of measure, warehouses, locations and reordering rules**. It does not store or
change stock quantities. Receipts, deliveries, transfers, adjustments and the stock ledger belong to
the inventory module, which references these records by ID.

## Architecture

```text
backend/app/
├── categories/      models, schemas, services, routes   → /api/categories
├── units/           …                                    → /api/units
├── warehouses/      …                                    → /api/warehouses
├── locations/       …                                    → /api/locations
├── products/        … + events.py (initial-stock hook)  → /api/products
├── reorder_rules/   …                                    → /api/reorder-rules
├── seeds/master_data.py   development/demo seed
└── core/            shared helpers added for list/CRUD endpoints (usable by any module):
    ├── pagination.py   Page[T], PageParamsDep (limit/offset), paginate(), contains() search
    ├── crud.py         get_or_404, get_reference, ensure_unique, commit_or_conflict, delete_or_conflict
    ├── errors.py       field_error / conflict / not_found / in_use (FastAPI error shape)
    ├── schemas.py      ORMModel, PatchModel (partial updates, rejects unknown fields)
    └── types.py        Name, Code, Sku, OptionalText, Quantity, UTCDatetime

frontend/src/
├── modules/master-data/   api.ts, types.ts, validation.ts, hooks.ts,
│                          SimpleEntityPage.tsx (list + form for simple records), LocationsManager.tsx
├── pages/master-data/     Products, ProductForm, ProductDetail, Categories, Units,
│                          Warehouses, WarehouseDetail, Locations, ReorderRules
├── components/ui/         + Pagination, StatusBadge, PageHeader, CheckboxField
└── test-utils/mockApi.tsx fetch mock + renderApp helper for page tests
```

Changes to shared files are limited to the extension points the auth module documented:
- Router registration in `app/main.py` and model imports in `app/models.py`.
- Routes in `src/App.tsx` and sidebar entries in `NAV_ITEMS`.
- A new "Master data" section appended to `global.css`.
- A listener in `app/core/database.py` that turns on foreign-key enforcement for SQLite connections, so
  local development and tests enforce the same delete rules as PostgreSQL.

Authentication itself was not modified.

## Data model

All tables have an integer `id`, `is_active`, `created_at` and `updated_at`.

| Table | Columns | Rules |
|-------|---------|-------|
| `categories` | `name` (100), `description` (500, nullable) | name unique (case-insensitive) |
| `units_of_measure` | `name` (50), `symbol` (16) | name and symbol each unique (case-insensitive); no conversions |
| `warehouses` | `name` (100), `code` (32), `address` (500, nullable) | name unique; code unique, stored upper-case |
| `locations` | `warehouse_id` → warehouses, `name` (100), `code` (32) | belongs to exactly one warehouse; name and code unique **within** the warehouse; `warehouse_id` cannot change after creation |
| `products` | `name` (100), `sku` (64), `category_id` → categories, `unit_of_measure_id` → units_of_measure, `initial_stock` numeric(14,3), `initial_location_id` → locations (nullable) | SKU unique across all products (active or not), stored upper-case; `initial_stock ≥ 0` and fixed after creation |
| `reorder_rules` | `product_id` → products, `location_id` → locations, `minimum_quantity`, `target_quantity` numeric(14,3) | one rule per product+location; `minimum ≥ 0`; `target ≥ minimum` (also DB check constraints); product and location fixed after creation |

Codes and SKUs are trimmed, upper-cased and limited to letters, digits and `. _ / -`. Names are
whitespace-normalised. Quantities have at most 3 decimals and are returned as JSON numbers.

### Relationships and delete behaviour

```text
Category ──< Product >── UnitOfMeasure
                │
                ├──< ReorderRule >── Location >── Warehouse
                │
                └── initial_location ──> Location
```

| Reference | On delete of the referenced row |
|-----------|---------------------------------|
| product → category, product → unit | RESTRICT: the category/unit returns **409**; deactivate it instead |
| location → warehouse | RESTRICT: a warehouse with locations cannot be deleted |
| product → initial_location | RESTRICT: that location is part of the product's history |
| reorder_rule → product / location | CASCADE: rules are configuration of the product and are removed with it |

Deactivation is the normal way to retire a record:
- An **inactive** category, unit, warehouse, location or product cannot be newly referenced.
  New products can't use it, and new rules or initial stock can't target it; the API returns 422
  on that field.
- Records that already reference it keep working. For example, a product whose category was archived
  can still be edited.
- A location is only *usable* when both it and its warehouse are active.

## API endpoints

All paths are under `/api`, and every endpoint requires `Authorization: Bearer <token>` (401 without).
**Any signed-in user can read.** Only `INVENTORY_MANAGER` users can create, update or delete;
`WAREHOUSE_STAFF` gets 403.

| Resource | Endpoints | List filters (all optional) |
|----------|-----------|-----------------------------|
| Products | `GET/POST /products`, `GET/PATCH/DELETE /products/{id}` | `q` (name or SKU), `category_id`, `unit_of_measure_id`, `is_active` |
| Categories | `GET/POST /categories`, `GET/PATCH/DELETE /categories/{id}` | `q` (name), `is_active` |
| Units | `GET/POST /units`, `GET/PATCH/DELETE /units/{id}` | `q` (name or symbol), `is_active` |
| Warehouses | `GET/POST /warehouses`, `GET/PATCH/DELETE /warehouses/{id}` | `q` (name or code), `is_active` |
| Locations | `GET/POST /locations`, `GET/PATCH/DELETE /locations/{id}` | `warehouse_id`, `q` (name or code), `is_active` |
| Reorder rules | `GET/POST /reorder-rules`, `GET/PATCH/DELETE /reorder-rules/{id}` | `product_id`, `location_id`, `warehouse_id`, `is_active` |

**Lists** accept `limit` (1–500, default 50) and `offset`, and return:

```json
{ "items": [...], "total": 42, "limit": 50, "offset": 0 }
```

Products are sorted by name, other lists by name/code, and rules by id. `q` is a case-insensitive
substring match; `%` and `_` are matched literally.

**Create bodies** (fields marked ? are optional):

| Resource | Body |
|----------|------|
| Category | `name`, `description?`, `is_active?` |
| Unit | `name`, `symbol`, `is_active?` |
| Warehouse | `name`, `code`, `address?`, `is_active?` |
| Location | `warehouse_id`, `name`, `code`, `is_active?` |
| Product | `name`, `sku`, `category_id`, `unit_of_measure_id`, `initial_stock?` (default 0), `initial_location_id?` (required when `initial_stock > 0`), `is_active?` |
| Reorder rule | `product_id`, `location_id`, `minimum_quantity`, `target_quantity`, `is_active?` |

**PATCH** accepts any subset of the editable fields. Unknown fields and `null` for required fields
return 422. These fields are not editable:
- product: `initial_stock`, `initial_location_id`
- location: `warehouse_id`
- rule: `product_id`, `location_id`

**Response shapes.** Records include their foreign-key IDs plus small nested summaries, so lists can be
displayed without extra calls:

```json
// GET /api/products/1
{
  "id": 1, "name": "Steel Rods", "sku": "STL-ROD",
  "category_id": 1, "category": {"id": 1, "name": "Raw Materials"},
  "unit_of_measure_id": 1, "unit_of_measure": {"id": 1, "name": "Kilogram", "symbol": "kg"},
  "initial_stock": 100.0, "initial_location_id": 3,
  "initial_location": {"id": 3, "name": "Rack A", "code": "RACK-A", "is_active": true,
                       "warehouse": {"id": 1, "name": "Main Warehouse", "code": "WH-MAIN", "is_active": true}},
  "is_active": true, "created_at": "2026-09-26T06:00:00Z", "updated_at": "2026-09-26T06:00:00Z"
}
```

Locations include `warehouse` ({id, name, code, is_active}). Reorder rules include `product`
({id, name, sku, is_active}) and `location` (same shape as above).

**Errors** use FastAPI's shape. Field problems come back as `detail: [{loc: ["body", "<field>"], msg}]`
so the UI can show them next to the field:

| Status | When |
|--------|------|
| 404 | record not found |
| 409 | duplicate SKU/name/code, duplicate rule, or delete of a record still in use (`detail` suggests deactivating) |
| 422 | validation error, or referenced category/unit/warehouse/location/product missing or inactive |

## Validation rules

| Record | Rules (API enforces; UI mirrors) |
|--------|----------------------------------|
| Product | name required (≤100); SKU required (≤64, code characters), unique; category and unit exist and are active; initial stock ≥ 0 with ≤ 3 decimals; initial stock > 0 needs a usable location |
| Category | name required (≤100), unique |
| Unit | name (≤50) and symbol (≤16) required, each unique |
| Warehouse | name required, unique; code required (≤32, code characters), unique |
| Location | active warehouse required; name and code required, each unique within the warehouse |
| Reorder rule | active product; usable location; minimum ≥ 0; target ≥ minimum; one rule per product+location |

## Frontend pages

| Route | Page | Who can edit |
|-------|------|--------------|
| `/products` | table with search (name/SKU), category and status filters, pagination | managers see **New product** |
| `/products/new`, `/products/:id/edit` | product form (initial stock + location on create only) | managers only (others are redirected) |
| `/products/:id` | details, initial stock, reorder rules, activate/deactivate | managers |
| `/categories`, `/units`, `/warehouses` | list + search + status filter + inline add/edit + activate/deactivate | managers |
| `/warehouses/:id` | warehouse details and its locations (add/edit/deactivate) | managers |
| `/locations` | locations across warehouses, warehouse filter | managers |
| `/reorder-rules` | rules with product/warehouse/status filters; add/edit/deactivate/delete; `?product_id=` pre-filters | managers |

Staff see the same pages read-only.

## Local setup

Follow the Quick start in the [README](../README.md). After `alembic upgrade head`, you can load demo data:

```bash
cd backend
python -m app.seeds.master_data     # development only; refuses when ENVIRONMENT=production
```

It creates the following, each labelled "Demo data for local development":
- category **Raw Materials**
- units **Kilogram (kg)** and **Piece (pc)**
- warehouse **Main Warehouse** (`DEMO-MAIN`) with **Rack A** and **Rack B**

It is idempotent. To create or edit master data in the UI, sign up as an **Inventory Manager**.

### Tests

```bash
cd backend && python -m pytest tests/master_data   # 115 tests
cd frontend && npm test                            # includes src/modules/master-data/__tests__
```

## Integration notes

### For Ravi (inventory operations)

- **IDs to reference:**
  - `products.id`
  - `locations.id`: stock lives per product and location
  - `warehouses.id`
  - `units_of_measure.id` (via `product.unit_of_measure_id`)
  - `reorder_rules.id`

  Declare your foreign keys with `ondelete="RESTRICT"`. The master-data DELETE endpoints then
  automatically return 409 ("deactivate instead") for any product or location your records use.
- **Only operate on usable records.** Products must have `is_active`. Locations must have `is_active`
  and `warehouse.is_active`; see `Location.is_usable` and `app.locations.services.get_usable_location(db, id, field=...)`.
  Locations belong to one warehouse, so a transfer between warehouses is simply a move between two
  locations.
- **Initial stock:** the product module records what was entered but never keeps a stock counter.
  Register a handler to turn it into your opening stock record:

  ```python
  # e.g. in app/inventory/services.py (make sure the module is imported at startup, e.g. by your router)
  from app.products.events import on_initial_stock

  @on_initial_stock
  def create_opening_stock(db, product, created_by):
      db.add(StockMove(product_id=product.id, location_id=product.initial_location_id,
                       quantity=product.initial_stock, created_by_id=created_by.id, ...))
  ```

  - The handler runs inside the product-creation transaction, after the product is flushed and before
    commit. **Don't commit** in it.
  - If it raises, the product is not created. Raise an `HTTPException` to control the response.
  - It is only called when `initial_stock > 0`. `initial_location_id` is then always set and usable.
  - Products created before your handler existed have `initial_stock` / `initial_location_id` stored,
    so you can backfill from them.
- **Quantities:** use the same column type, `app.products.models.QUANTITY_TYPE` (`Numeric(14, 3)`), and
  `app.core.types.Quantity` in schemas.
- **Stock per location on the product page:** `ProductDetailPage.tsx` has a marked spot for it.
- **Changing a product's unit of measure is currently allowed.** If you want to lock the unit once stock
  moves exist, add that check in `app/products/services.update_product`.

### For Maheshwar (dashboard, ledger, alerts)

- **Filter dropdowns:**
  - `GET /api/categories?is_active=true&limit=500`
  - `GET /api/warehouses?...`
  - `GET /api/locations?warehouse_id=...`
- **Low stock / reorder:** for each active rule (`GET /api/reorder-rules?is_active=true`, optionally
  filtered by `warehouse_id` or `product_id`), compare the stock on hand at `rule.location_id` from
  the inventory module. `stock <= minimum_quantity` means reorder, and the suggested quantity is
  `target_quantity - stock`. Skip rules whose product or location is inactive.
- **In SQL:** join `reorder_rules` to your stock table on `(product_id, location_id)`.
- **Category filter on stock or moves:** join `products.category_id`.
- **Warehouse filter:** join `locations.warehouse_id`.

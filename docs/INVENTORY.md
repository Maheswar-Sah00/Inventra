# Inventory Operations & Stock Engine

Owner: Ravi Varma. This module owns the transactional core:
- **stock quantities per product and location**
- **receipts, delivery orders, internal transfers and inventory adjustments**
- the **stock movement ledger**

It builds on the auth module (users, `CurrentUser`) and the master-data module (products, locations,
warehouses, reorder rules). It creates no product, warehouse or user tables of its own.

## Architecture

```text
backend/app/
├── inventory/
│   ├── models.py      Stock (one row per product+location), StockMovement (ledger), MovementType
│   ├── services.py    the stock engine: StockOperation (lock → change → record movement); initial-stock hook
│   ├── documents.py   shared document lifecycle: statuses, references, compare-and-set transitions, list filters
│   ├── queries.py     read-only stock, per-product availability, reorder status, ledger queries
│   ├── schemas.py     shared response shapes (UserRef, LineOut, StockOut, MovementOut, …)
│   └── routes.py      /api/stock, /api/stock/products/{id}, /api/stock-movements
├── receipts/          Receipt + ReceiptItem              → /api/receipts
├── deliveries/        Delivery + DeliveryItem (pick/pack) → /api/deliveries
├── transfers/         Transfer + TransferItem            → /api/transfers
└── adjustments/       Adjustment + AdjustmentItem        → /api/adjustments

frontend/src/
├── modules/inventory/   api.ts, types.ts, operations.ts (per-operation config), DocumentStatusBadge, ProductStockPanel
└── pages/operations/    OperationListPage / OperationFormPage / OperationDetailPage (shared by all four)
```

**One authoritative source.** Only `app/inventory/services.py` writes to `stock`, and every change it
makes writes a `stock_movements` row in the same transaction. Documents hold what was requested (their
lines), never a running quantity.

Integration points in teammates' code, all at the places they documented for extension:
- routers in `app/main.py`, models in `app/models.py`
- routes in `src/App.tsx`, sidebar `NAV_SECTIONS`
- the stock panel slot in `ProductDetailPage.tsx`, plus its test mock
- a new section in `global.css`

The product module's `on_initial_stock` hook is implemented here: a product created with initial stock
gets a stock row and an `INITIAL_STOCK` movement in the same transaction.

## Stock model

`stock`:
- `id`
- `product_id` → products (RESTRICT)
- `location_id` → locations (RESTRICT)
- `quantity` numeric(14,3), **CHECK quantity ≥ 0**
- `created_at`, `updated_at`

**UNIQUE (product_id, location_id).** "Steel @ Rack A" and "Steel @ Rack B" are separate positions.
Totals per product or warehouse are sums of positions. Positions are created on first use; positions at 0
are kept but hidden from `/api/stock` unless `include_empty=true`.

## Stock movement model (ledger)

`stock_movements`:

| Column | Meaning |
|--------|---------|
| `product_id` | what |
| `movement_type` | `INITIAL_STOCK`, `RECEIPT`, `DELIVERY`, `TRANSFER`, `ADJUSTMENT` |
| `quantity` | how much; signed, see below; never 0 |
| `source_location_id` | from where (null when stock enters the company) |
| `destination_location_id` | to where (null when stock leaves); at least one location is always set |
| `reference_type`, `reference_id`, `reference_number` | which document, e.g. `RECEIPT`, 12, `REC-000012`. For initial stock: `PRODUCT`, product id, SKU |
| `performed_by_id` → users | who validated |
| `created_at` | when |

| Type | quantity | source | destination |
|------|----------|--------|-------------|
| RECEIPT / INITIAL_STOCK | +X | null | receiving location |
| DELIVERY | −X | shipping location | null |
| TRANSFER | +X (moved amount) | from | to |
| ADJUSTMENT (gain) | +difference | null | location |
| ADJUSTMENT (loss) | −difference | location | null |

`quantity` is the effect on total on-hand stock, except for transfers, which record the moved amount.
Per-location effect for any row: **−|quantity| at `source_location_id`, +|quantity| at
`destination_location_id`**. Movements are append-only; the API never updates or deletes them.

## Document lifecycle (all four operations)

```text
DRAFT ──confirm──▶ READY  (or WAITING: not enough stock at the source yet; confirm again re-checks)
  │                  │
  └──── validate ────┴──▶ DONE      stock changes here, once
  any open status ──cancel──▶ CANCELED
```

- **Statuses:** `DRAFT`, `WAITING`, `READY`, `DONE`, `CANCELED`. The last two are final. A done document
  is corrected with a new document, such as a reverse transfer or an adjustment.
- **Only validation changes stock.** Drafts, confirmations, picking and packing never do.
- **Editing** (`PATCH`) is allowed while the document is open. It returns the document to `DRAFT` and,
  for deliveries, clears pick/pack. Lines are replaced as a whole.
- **Idempotent.** `validate` on a `DONE` document returns it unchanged with 200 and moves no stock, so a
  refresh or retried request is safe. `cancel` on a `CANCELED` document also returns 200. `confirm` on a
  `READY` document is a no-op. Invalid transitions (validating a canceled document, cancelling a done one,
  editing a done one) return **409**.
- **References** such as `REC-000001`, `DEL-000001`, `TRF-000001`, `ADJ-000001` are derived from the
  internal id and unique.
- **Lines:** at least one per document and one per product (combine quantities). Products must be
  active and locations usable (location and warehouse active). This is checked on create/edit and again
  at validation.
- **Stock is not reserved.** Availability shown at confirm and pick is a hint; validation re-checks under
  lock and is authoritative.

### Receipts (incoming)

- **Fields:** `supplier_name` (required), `supplier_reference`, `destination_location_id`,
  `scheduled_date`, `notes`, `items[{product_id, quantity > 0}]`.
- **Validate:** each line adds to stock at the destination and records a `RECEIPT` +X movement.
  Example: 100 + 50 → 150.

### Delivery orders (outgoing)

- **Fields:** `customer_name`, `source_location_id`, `scheduled_date`, `notes`, `items`.
- **Flow:** `confirm` (READY if the source has enough of every line, otherwise WAITING) → `pick` → `pack` → `validate`.
- Pick and pack need `READY`, happen in order, and record `picked_at/by` and `packed_at/by`. Pick
  re-checks availability. Status stays `READY` during picking and packing, so dashboards see the standard
  five statuses.
- **Validate** requires a packed order. Every line must be available (**all or nothing**), otherwise
  409 with the shortages, e.g. `Not enough stock: CHR at MAIN / Rack A (available 3, requested 6)`, and
  nothing changes. On success stock decreases and `DELIVERY` −X movements are recorded.

### Internal transfers

- **Fields:** `source_location_id`, `destination_location_id`, `scheduled_date`, `notes`, `items`.
  Source and destination must differ (422, plus a DB check constraint). They can be in the same or
  different warehouses.
- **Validate:** each line leaves the source and arrives at the destination, all or nothing. Total stock
  is unchanged. One `TRANSFER` movement per line carries both locations. Example: A 100 / B 20, move 30 →
  A 70 / B 50, total 120 → 120.

### Inventory adjustments

- **Fields:** `location_id`, `reason` (required), `notes`, `items[{product_id, counted_quantity ≥ 0}]`.
- **Validate:** for each line, under lock:
  - `recorded_quantity` = current stock and `difference = counted − recorded`, both stored on the line
  - stock becomes `counted_quantity`
  - an `ADJUSTMENT` movement records the difference; no movement when the difference is 0

  The recorded quantity is taken at validation, not at creation, so stock movements between counting and
  validating are accounted for. While open, `current_quantity` shows live stock. Example: 100 recorded,
  97 counted → difference −3, stock 97.

## Transactions and concurrency

Every stock-changing request runs in a single database transaction:

```text
1. compare-and-set the document:  UPDATE <doc> SET status='DONE', validated_by… WHERE id=? AND status IN (open)
   → 0 rows: someone else already acted → return the current state (DONE) or 409
2. lock stock rows:  SELECT … FROM stock WHERE product_id=? AND location_id=? FOR UPDATE OF stock
   (rows created first if missing via INSERT … ON CONFLICT DO NOTHING; always locked in
   (product_id, location_id) order to avoid deadlocks)
3. check availability on the locked rows with exact Decimal arithmetic; collect all shortages
4. update stock rows + insert stock_movements rows
5. COMMIT, or ROLLBACK on any error (shortage, validation error, failed insert): the DONE status is
   rolled back too, so the document stays open and can be retried
```

- **PostgreSQL:** step 1 takes a row lock on the document, so a concurrent validate of the same document
  waits and then updates 0 rows. Step 2 row-locks the stock positions, so two documents touching the
  same position serialise and the second sees the first's result. With 10 in stock and deliveries of 7
  and 6 validated at once, one succeeds and the other gets 409.
- **SQLite** (local dev/tests) ignores `FOR UPDATE`. Step 1 is the transaction's first write and takes
  the database write lock, which serialises the rest just as well.
- **Database guards as a last line of defence:**
  - `CHECK (quantity >= 0)` on stock
  - `CHECK (quantity > 0)` on receipt, delivery and transfer lines; `CHECK (counted_quantity >= 0)` on
    adjustment lines
  - `CHECK (quantity <> 0)` on movements
  - `UNIQUE (product_id, location_id)` on stock

**Verified by tests:**
- Stock and status are fully rolled back when the movement insert fails.
- Concurrent tests use real threads with separate connections on a file-backed SQLite database:
  - two competing deliveries → exactly one succeeds
  - four simultaneous validations of one delivery → stock moves once
  - two receipts into a new position → both land
  - with the compare-and-set disabled, the double-validation test fails, which confirms it detects the race
- **Not run against a live PostgreSQL server** (none was available). The generated migration SQL and the
  `FOR UPDATE OF stock` query were checked by compiling them for the PostgreSQL dialect.

## Business rules summary

| Operation | Rules (enforced by the API) |
|-----------|-----------------------------|
| All | authenticated user; ≥1 line; one line per product; products exist and are active; locations exist, are active, and in an active warehouse; quantities ≤ 3 decimals; only open documents can be edited, validated or canceled |
| Receipt | quantity > 0; supplier required |
| Delivery | quantity > 0; confirmed, picked and packed before validation; sufficient stock at validation (all or nothing) |
| Transfer | quantity > 0; source ≠ destination; sufficient source stock at validation (all or nothing) |
| Adjustment | counted ≥ 0; reason required |

**Permissions:** every signed-in, active user can run all operations. Both roles in the brief handle
stock: managers do incoming and outgoing, staff do transfers, picking and counting. To restrict one, add
`dependencies=[Depends(require_roles(UserRole.INVENTORY_MANAGER))]` to its route. `created_by`,
`validated_by`, `picked_by` and `packed_by` record who did what.

## API endpoints

All under `/api`; all require `Authorization: Bearer <token>`.

**Documents.** The same pattern applies to `receipts`, `deliveries`, `transfers` and `adjustments`:

| Method | Path | Notes |
|--------|------|-------|
| GET | `/{kind}` | Filters: `status` (repeatable: `?status=DRAFT&status=WAITING&status=READY` = pending), `q` (reference, supplier/customer/reason), `location_id`, `warehouse_id` (transfers: either side), `product_id`, `category_id` (documents containing a matching line), `limit`, `offset`. Newest first. |
| POST | `/{kind}` | create (201, `DRAFT`) |
| GET | `/{kind}/{id}` | detail; open deliveries/transfers include `available_quantity` per line, open adjustments `current_quantity` |
| PATCH | `/{kind}/{id}` | edit header fields and/or replace `items` (open documents only; resets to `DRAFT`) |
| POST | `/{kind}/{id}/confirm` | → READY (receipts, adjustments) or READY/WAITING by availability (deliveries, transfers) |
| POST | `/deliveries/{id}/pick`, `/deliveries/{id}/pack` | delivery preparation steps |
| POST | `/{kind}/{id}/validate` | apply to stock (idempotent) |
| POST | `/{kind}/{id}/cancel` | cancel an open document (idempotent) |

Common document fields: `id`, `reference`, `status`, `scheduled_date`, `notes`, `created_by{id,name}`,
`validated_by`, `validated_at`, `canceled_at`, `created_at`, `updated_at`, and `items[]` with
`product{id,name,sku,is_active,unit_of_measure}`.

**Stock (read-only):**

| Method | Path | Returns |
|--------|------|---------|
| GET | `/stock` | positions `{id, product_id, product{…, category, unit_of_measure}, location_id, location{…, warehouse}, quantity, updated_at}`. Filters: `product_id`, `location_id`, `warehouse_id`, `category_id`, `q` (name/SKU), `include_empty` |
| GET | `/stock/products/{product_id}` | `{product, total_quantity, locations[{location, quantity}]}`; optional `warehouse_id` |
| GET | `/stock-movements` | ledger `{id, movement_type, product, quantity, source_location, destination_location, reference_type, reference_id, reference_number, performed_by, created_at}`, newest first. Filters: `product_id`, `location_id`/`warehouse_id` (either side), `category_id`, `movement_type` (repeatable), `reference_type`, `reference_id`, `date_from`, `date_to` (UTC dates, inclusive), `q` (product or reference) |

All lists return `{items, total, limit, offset}`. Quantities are JSON numbers.

**Errors:**

| Status | When |
|--------|------|
| 404 | not found |
| 409 | invalid transition for the current status, or not enough stock (`detail` lists every shortage) |
| 422 | validation (bad quantity, missing field, same source/destination, unknown or inactive product/location) |

## Frontend

| Route | Page |
|-------|------|
| `/receipts`, `/deliveries`, `/transfers`, `/adjustments` | list with status filter (default *Pending*), search, warehouse filter |
| `/{kind}/new`, `/{kind}/:id/edit` | form: header fields, product lines. Deliveries and transfers show available stock per line with an "Only X available" warning; adjustments show recorded stock and live difference |
| `/{kind}/:id` | detail with the actions valid for the current status (Confirm/Check availability, Pick, Pack, Validate, Cancel with confirmation, Edit), line availability, and the resulting stock movements once done |
| `/stock` | current stock by product and location with search and warehouse filter |
| `/products/:id` | now shows **Stock on hand**: total and per location |

## Integration contract for Maheshwar (dashboard, ledger, move history)

Dashboard KPIs:

| Need | Call |
|------|------|
| Total products in stock | `GET /api/stock` (positions with quantity > 0; distinct `product_id`s), or `GET /api/stock/products/{id}` per product |
| Low stock / out of stock | `GET /api/stock-availability?status=LOW_STOCK&status=OUT_OF_STOCK` (dashboard module; see [DASHBOARD.md](DASHBOARD.md)) |
| Pending receipts | `GET /api/receipts?status=DRAFT&status=WAITING&status=READY&limit=1` → `total` |
| Pending deliveries | same on `/api/deliveries` |
| Internal transfers scheduled | same on `/api/transfers` (`scheduled_date` available per document) |

Dynamic filters:
- **Document type:** choose the endpoint, or use `movement_type` on the ledger.
- **Status:** `status=` (the five values above).
- **Warehouse or location:** `warehouse_id` / `location_id`.
- **Product category:** `category_id`. This works on the documents, `/stock` and `/stock-movements`.

**Move history / stock ledger:** `GET /api/stock-movements` with the filters above. Link each row to its
document using `reference_type` and `reference_id`. `reference_type` is one of `RECEIPT`, `DELIVERY`,
`TRANSFER`, `ADJUSTMENT`, or `PRODUCT` (initial stock).

**Don't rebuild stock from the ledger.** `/api/stock` is the current state; the ledger is history.
Summing a product's movements per location gives the same answer.

## Assumptions

- There is no negative stock (the brief doesn't mention it) and no reservations or backorders.
- A delivery ships from one location and a transfer moves between one pair of locations. Moving from
  several locations takes several documents.
- Suppliers and customers are free-text fields on the document, not a separate directory.
- Cancelling a `DONE` document is not allowed. Reverse it with a new document so the ledger stays
  truthful.
- Deleting a product, location or warehouse that stock or movements reference is refused by the master-data
  module (409, "deactivate instead") thanks to `ondelete=RESTRICT` on every foreign key here.

## Tests

```bash
cd backend && python -m pytest tests/inventory      # 57 tests
cd frontend && npm test                             # includes src/modules/inventory/__tests__
```

Backend coverage by file:
- `test_receipts.py`, `test_deliveries.py`, `test_transfers.py`, `test_adjustments.py`: each operation's rules
- `test_stock_api.py`: stock and ledger APIs, initial stock, rollback on a failed movement insert
- `test_concurrency.py`: real concurrent validations
- `test_migration.py`: upgrade and downgrade

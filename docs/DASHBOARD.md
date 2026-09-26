# Dashboard, Stock Availability & Move History

Owner: Maheshwar. This is the visibility layer:
- the **Inventory Dashboard** (landing page after login)
- **Stock Availability** with low-stock and out-of-stock status
- **Move History** (the stock ledger)

It is **read-only**. It stores no data of its own: stock comes from the inventory engine (`stock`),
history from `stock_movements`, documents from the receipt/delivery/transfer/adjustment tables, and
thresholds from reorder rules. There is no dashboard table, cache or second stock counter.

## Architecture

```text
backend/app/dashboard/
├── services.py   SQL aggregation: KPI summary, document counts, stock availability + status
├── schemas.py    DashboardSummary, AvailabilityRow, StockStatus, DocumentType
└── routes.py     GET /api/dashboard/summary, GET /api/stock-availability

frontend/src/
├── modules/dashboard/   api.ts, hooks.ts (URL filters, loading/error/retry), components.tsx
│                        (KpiCard, StockStatusBadge, ScopeFilters, MovementTable, Error/EmptyState)
└── pages/dashboard/     DashboardPage (/dashboard), StockAvailabilityPage (/stock-availability),
                         MoveHistoryPage (/move-history)
```

**Reused, not duplicated:**
- auth: `CurrentUser` guard on every endpoint; `ProtectedRoute`/`useAuth` on every page
- master data: warehouse/location/category APIs for filter options; reorder rules for thresholds
- inventory: `stock`, `stock_movements`, document models, `OPEN_STATUSES`, and
  `documents.filter_documents` for the category filter. The ledger, activity feed and stock endpoints
  already existed (`/api/stock-movements`, `/api/stock`), so no new endpoints were added for them.

## KPI definitions (`GET /api/dashboard/summary`)

| KPI | Definition |
|-----|------------|
| **Total Products in Stock** | Distinct active products with on-hand quantity > 0 in at least one position in scope (sum over `stock`) |
| **Low Stock** | Positions with status `LOW_STOCK` (see below) |
| **Out of Stock** | Positions with status `OUT_OF_STOCK` |
| **Pending Receipts** | Receipts with status DRAFT, WAITING or READY |
| **Pending Deliveries** | Delivery orders with status DRAFT, WAITING or READY |
| **Internal Transfers Scheduled** | Transfers with status DRAFT, WAITING or READY (not done or canceled) |

DONE and CANCELED documents are never counted as pending. The response also includes `documents`, with
counts per document type and status for the "Operations by status" table.

### Stock status (the alert logic)

Status is computed in one SQL expression, used by both the KPIs and the availability list, so a KPI and
the list it links to always agree:

```text
on hand == 0                                              → OUT_OF_STOCK
active reorder rule for product+location and on hand <= minimum  → LOW_STOCK
otherwise                                                 → IN_STOCK
```

- **Positions evaluated:** every active product at every location that has a `stock` row, plus every
  location with an active reorder rule (at an active location and warehouse). A monitored location that
  never received stock therefore shows as out of stock at 0.
- **Low stock needs a reorder rule.** A product without rules can only be `OUT_OF_STOCK` (at a location
  it was emptied from) or `IN_STOCK`.
- **"At or below minimum"** matches the reorder-rule semantics. This is the only implementation of
  the rule; the inventory module's former `/api/stock/reorder-status` was removed during integration.
- **Alerts are in-app only:** the dashboard's *Stock alerts* panel plus status badges. There is no
  email, SMS or push. Status is always written out ("Low stock"), never shown by colour alone.

## Filters

All dashboard filters live in the URL (`/dashboard?warehouse_id=2&status=READY`), so links and refreshes
keep them. Options are loaded from the master-data APIs; the location list narrows to the chosen
warehouse.

| Filter | Stock KPIs & alerts | Document KPIs & table | Recent activity |
|--------|---------------------|-----------------------|-----------------|
| Warehouse / Location | positions in scope | document location (receipt → destination, delivery → source, transfer → **either side**, adjustment → location) | movements touching it (either side) |
| Category | products in the category | documents with at least one line in the category | products in the category |
| Document type | no effect | only that type; other operation KPIs show "—" | matching movement type |
| Status | no effect | KPIs count **that status** instead of "pending" (card label changes, e.g. "Receipts · Ready"); the table shows that column | no effect (stock only moves when a document is done) |

**Validation.** Malformed values (unknown document type or status, non-numeric or ≤ 0 IDs) return 422.
Unknown warehouse, location or category IDs, or a location outside the selected warehouse, also return
422 (`detail[0].loc = ["query", "<field>"]`) rather than silently showing zeros. The page shows
"Invalid filter: …" with a Retry button.

**KPI links:**
- The stock cards open `/stock-availability` with the same scope and matching statuses.
- The operation cards open `/receipts`, `/deliveries` or `/transfers`, carrying `status` and `warehouse_id`.
  Those list pages now read these two parameters from the URL (a small change to `OperationListPage`);
  with none given they still default to *Pending*.
- Counts in the operations table link to the list filtered to that status.

## Stock availability (`GET /api/stock-availability`, page `/stock-availability`)

- **Rows:** product (with SKU and unit), category, location (with warehouse), on-hand quantity, and the
  reorder rule's minimum/target (null without a rule).
- **Status** is computed as above. Rows are sorted most urgent first (out → low → in), then by product,
  warehouse and location.
- **Filters:** `warehouse_id`, `location_id`, `category_id`, `product_id`, `q` (name/SKU), and `status`
  (repeatable: `IN_STOCK`, `LOW_STOCK`, `OUT_OF_STOCK`). Paginated with `limit`/`offset`, returning
  `{items, total, limit, offset}`.
- The page is read-only. It is the single stock page: the inventory module's earlier `/stock` page was
  removed during integration, and `/stock` now redirects here.

## Move History / Stock Ledger (page `/move-history`)

The page reads the inventory module's ledger, `GET /api/stock-movements`:
- **Columns:** date/time, movement type, product (with SKU), signed quantity with unit, from location,
  to location, reference (linking to the document or product), performed by.
- **Filters:** search (product name, SKU or document reference), movement type (`INITIAL_STOCK`,
  `RECEIPT`, `DELIVERY`, `TRANSFER`, `ADJUSTMENT`, the backend values), warehouse, location (either
  side), category, date range (UTC, inclusive; "to" before "from" is flagged), and `product_id` via URL.
- **Pagination:** server-side, 25 per page. It shows "Page X of Y · first–last of total" with
  Previous/Next, and changing a filter returns to page 1.

The dashboard's *Recent activity* is the same endpoint with `limit=8`. Current stock is never rebuilt by
replaying movements in the browser.

## States

- **Loading:** each section loads on its own ("Loading…" in KPI cards, "Loading inventory…",
  "Loading ledger…").
- **Empty:** zero results is not an error. Examples: "No low-stock or out-of-stock items.", "No documents
  match these filters.", "No stock movements yet.", "No stock matches these filters.".
- **Errors:** each section shows the API's message with a **Retry** button. Invalid filters are shown as
  such. An expired or revoked session is handled by the shared API client, which signs out and
  redirects to `/login`.

## Access

Every signed-in, active user can view everything, whether an Inventory Manager or Warehouse Staff
member; there are no extra role rules. Unauthenticated API calls get 401, and pages redirect to
`/login`.

## API summary

| Endpoint | Owner | Used for |
|----------|-------|----------|
| `GET /api/dashboard/summary` | **new (dashboard)** | KPIs and operations table |
| `GET /api/stock-availability` | **new (dashboard)** | stock alerts panel, Stock Availability page |
| `GET /api/stock-movements` | inventory | recent activity, Move History |
| `GET /api/warehouses`, `/locations`, `/categories` | master data | filter options |
| `GET /api/receipts`, `/deliveries`, `/transfers` | inventory | lists opened from KPI links |

The brief's conceptual `/stock-movements/{id}`, `/move-history` and `/dashboard/activity` endpoints
were not added: the existing ledger endpoint with filters covers them.

## Changes outside this module

| File | Change | Why |
|------|--------|-----|
| `backend/app/main.py` | register the dashboard router | documented extension point |
| `frontend/src/App.tsx` | `/dashboard` → `DashboardPage`; add `/stock-availability`, `/move-history`; removed the auth module's `DashboardPlaceholderPage` | the placeholder was meant to be replaced |
| `AppLayout.tsx` navigation | add *Move History* and *Stock Availability*; grouped into sections during integration (`NAV_SECTIONS`) | documented extension point |
| `components/ui/Pagination.tsx` | add "Page X of Y" | brief asks for a current-page indicator; applies to every list |
| `pages/operations/OperationListPage.tsx` | initial `status`/`warehouse_id` from the URL | so dashboard links open pre-filtered lists |
| `docs/AUTH.md` | the placeholder mention now points here | file removed |

## Running the end-to-end check

- **Automated:** `backend/tests/dashboard/test_end_to_end.py` runs the brief's full flow through the real
  APIs and asserts stock, KPIs, availability, low stock and the ledger:
  create product, warehouse and locations → receive 100 → transfer 30 → deliver 20 → count 8.
- **Manually:**
  1. Start the backend and frontend (see the README).
  2. Sign up as an Inventory Manager and create a category, unit, warehouse, two locations and a
     product.
  3. Run a receipt of 100, a transfer of 30, a delivery of 20 (confirm → pick → pack → validate) and an
     adjustment counting 8.
  4. Open **Dashboard**: 1 product in stock, nothing pending.
  5. Open **Stock**: 70 and 8.
  6. Open **Move History**: +100, 30, −20, −2, each linked to its document.

```bash
cd backend && python -m pytest tests/dashboard   # 21 tests
cd frontend && npm test                          # includes src/modules/dashboard/__tests__
```

## Assumptions

- "Pending" means DRAFT, WAITING or READY, from the inventory module's `OPEN_STATUSES`. "Scheduled
  transfers" uses the same definition; `scheduled_date` is optional and not required for counting.
- Low and out-of-stock counts are **per product and location**, not per product: a product can be low
  at one rack and fine at another. An emptied position without a rule counts as out of stock there.
- Inactive products are excluded from stock KPIs and availability. Reorder rules count only when the
  rule, its location and its warehouse are active.
- Adjustment documents appear in the operations table and in the document-type filter. The brief
  defines no adjustment KPI, so none was added.

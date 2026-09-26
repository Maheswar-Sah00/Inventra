import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { callsTo, mockApi, page, renderApp, signedInAs, type MockHandler } from "../../../test-utils/mockApi";
import { mainWarehouse, rackA, rawMaterials } from "../../master-data/__tests__/fixtures";
import type { StockMovement } from "../../inventory/types";
import type { AvailabilityRow, DashboardSummary } from "../types";

const secondWarehouse = { ...mainWarehouse, id: 2, name: "Second Warehouse", code: "WH2" };
const rackC = { ...rackA, id: 12, name: "Rack C", code: "RACK-C", warehouse_id: 2, warehouse: { id: 2, name: "Second Warehouse", code: "WH2", is_active: true } };
const product = { id: 100, name: "Steel Rods", sku: "STL-ROD", is_active: true, unit_of_measure: { id: 1, name: "Kilogram", symbol: "kg" } };

const lookups: Record<string, MockHandler> = {
  "GET /warehouses": () => ({ status: 200, body: page([mainWarehouse, secondWarehouse]) }),
  "GET /locations": () => ({ status: 200, body: page([rackA, rackC]) }),
  "GET /categories": () => ({ status: 200, body: page([rawMaterials]) }),
};

function summaryBody(overrides: Partial<DashboardSummary> = {}): DashboardSummary {
  const counts = { DRAFT: 0, WAITING: 0, READY: 0, DONE: 0, CANCELED: 0 };
  return {
    total_products_in_stock: 12,
    low_stock_items: 3,
    out_of_stock_items: 1,
    pending_receipts: 4,
    pending_deliveries: 2,
    scheduled_transfers: 5,
    counted_statuses: ["DRAFT", "WAITING", "READY"],
    documents: [
      { document_type: "RECEIPT", counts: { ...counts, DRAFT: 1, READY: 3, DONE: 7 }, total: 11 },
      { document_type: "DELIVERY", counts: { ...counts, WAITING: 2 }, total: 2 },
      { document_type: "TRANSFER", counts: { ...counts, READY: 5 }, total: 5 },
      { document_type: "ADJUSTMENT", counts, total: 0 },
    ],
    ...overrides,
  };
}

const lowRow: AvailabilityRow = {
  product,
  category: { id: 1, name: "Raw Materials" },
  location: rackA,
  quantity: 4,
  minimum_quantity: 10,
  target_quantity: 50,
  status: "LOW_STOCK",
};

function movement(id: number, overrides: Partial<StockMovement> = {}): StockMovement {
  return {
    id,
    movement_type: "RECEIPT",
    product_id: 100,
    product,
    quantity: 50,
    source_location_id: null,
    source_location: null,
    destination_location_id: 10,
    destination_location: rackA,
    reference_type: "RECEIPT",
    reference_id: 1,
    reference_number: "REC-000001",
    performed_by: { id: 1, name: "Sam Staff" },
    created_at: "2026-09-26T10:42:00Z",
    ...overrides,
  };
}

function dashboardRoutes(overrides: Record<string, MockHandler> = {}) {
  return {
    ...signedInAs("WAREHOUSE_STAFF"),
    ...lookups,
    "GET /dashboard/summary": () => ({ status: 200, body: summaryBody() }),
    "GET /stock-availability": () => ({ status: 200, body: page([lowRow], 4) }),
    "GET /stock-movements": () => ({ status: 200, body: page([movement(1)]) }),
    ...overrides,
  };
}

describe("dashboard", () => {
  it("shows KPIs from the summary API with links to the modules", async () => {
    mockApi(dashboardRoutes());
    renderApp("/dashboard");
    const kpis = await screen.findByLabelText("Key figures");
    const card = (label: string) => within(kpis).getByText(label).closest(".kpi-card") as HTMLElement;
    await waitFor(() => expect(within(card("Total Products in Stock")).getByText("12")).toBeInTheDocument());
    expect(within(card("Low / Out of Stock")).getByText("4")).toBeInTheDocument();
    expect(within(card("Low / Out of Stock")).getByText("3 low · 1 out of stock")).toBeInTheDocument();
    expect(card("Pending Receipts")).toHaveAttribute("href", "/receipts");
    expect(within(card("Pending Deliveries")).getByText("2")).toBeInTheDocument();
    expect(within(card("Internal Transfers Scheduled")).getByText("5")).toBeInTheDocument();
    expect(card("Low / Out of Stock")).toHaveAttribute("href", "/stock-availability?status=LOW_STOCK%2COUT_OF_STOCK");

    // Stock alerts, operations table and recent activity.
    expect(await screen.findByText("Low stock")).toBeInTheDocument();
    expect(screen.getByText("+3 more")).toBeInTheDocument();
    const operations = screen.getByRole("heading", { name: "Operations by status" }).closest("section")!;
    expect(within(operations).getByRole("link", { name: "7" })).toHaveAttribute("href", "/receipts?status=DONE");
    expect(await screen.findByRole("link", { name: "REC-000001" })).toHaveAttribute("href", "/receipts/1");
    expect(screen.getByText("+50 kg")).toBeInTheDocument();
  });

  it("shows empty states when there is no data", async () => {
    const empty = summaryBody({
      total_products_in_stock: 0,
      low_stock_items: 0,
      out_of_stock_items: 0,
      pending_receipts: 0,
      pending_deliveries: 0,
      scheduled_transfers: 0,
      documents: summaryBody().documents.map((d) => ({ ...d, counts: { DRAFT: 0, WAITING: 0, READY: 0, DONE: 0, CANCELED: 0 }, total: 0 })),
    });
    mockApi(
      dashboardRoutes({
        "GET /dashboard/summary": () => ({ status: 200, body: empty }),
        "GET /stock-availability": () => ({ status: 200, body: page([]) }),
        "GET /stock-movements": () => ({ status: 200, body: page([]) }),
      }),
    );
    renderApp("/dashboard");
    expect(await screen.findByText("No low-stock or out-of-stock items.")).toBeInTheDocument();
    expect(await screen.findByText("No documents match these filters.")).toBeInTheDocument();
    expect(await screen.findByText("No stock movements yet.")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("sends filters to every dashboard query and keeps them in the URL", async () => {
    const fetchMock = mockApi(dashboardRoutes());
    renderApp("/dashboard");
    const u = userEvent.setup();
    const filters = await screen.findByRole("form", { name: "Dashboard filters" });
    await screen.findByRole("option", { name: "Second Warehouse" });

    await u.selectOptions(within(filters).getByLabelText("Warehouse"), "2");
    await u.selectOptions(within(filters).getByLabelText("Category"), "1");
    await waitFor(() => {
      const last = callsTo(fetchMock, "GET", "/dashboard/summary").slice(-1)[0][0];
      expect(last.searchParams.get("warehouse_id")).toBe("2");
      expect(last.searchParams.get("category_id")).toBe("1");
    });
    const alerts = callsTo(fetchMock, "GET", "/stock-availability").slice(-1)[0][0];
    expect(alerts.searchParams.get("warehouse_id")).toBe("2");
    expect(alerts.searchParams.getAll("status")).toEqual(["OUT_OF_STOCK", "LOW_STOCK"]);
    expect(callsTo(fetchMock, "GET", "/stock-movements").slice(-1)[0][0].searchParams.get("category_id")).toBe("1");
    // Location options are narrowed to the chosen warehouse.
    expect(within(within(filters).getByLabelText("Location")).queryByRole("option", { name: "WH-MAIN / Rack A" })).not.toBeInTheDocument();
    expect(within(within(filters).getByLabelText("Location")).getByRole("option", { name: "WH2 / Rack C" })).toBeInTheDocument();
  });

  it("applies document type and status filters", async () => {
    const fetchMock = mockApi(
      dashboardRoutes({
        "GET /dashboard/summary": (url) => ({
          status: 200,
          body: summaryBody(
            url.searchParams.get("document_type") === "RECEIPT"
              ? { pending_deliveries: null, scheduled_transfers: null, pending_receipts: 3, counted_statuses: ["READY"] }
              : {},
          ),
        }),
      }),
    );
    renderApp("/dashboard?document_type=RECEIPT&status=READY");
    const kpis = await screen.findByLabelText("Key figures");
    await waitFor(() => expect(within(kpis).getByText("Receipts · Ready")).toBeInTheDocument());
    const receipts = within(kpis).getByText("Receipts · Ready").closest(".kpi-card")!;
    await waitFor(() => expect(within(receipts as HTMLElement).getByText("3")).toBeInTheDocument());
    expect(receipts).toHaveAttribute("href", "/receipts?status=READY");
    expect(within(kpis).getAllByText("Hidden by the document type filter")).toHaveLength(2);
    const request = callsTo(fetchMock, "GET", "/dashboard/summary")[0][0];
    expect(request.searchParams.get("status")).toBe("READY");
    expect(callsTo(fetchMock, "GET", "/stock-movements")[0][0].searchParams.get("movement_type")).toBe("RECEIPT");
  });

  it("shows invalid filters and API failures with a retry", async () => {
    let calls = 0;
    const fetchMock = mockApi(
      dashboardRoutes({
        "GET /dashboard/summary": () => {
          calls += 1;
          return calls === 1
            ? { status: 422, body: { detail: [{ loc: ["query", "warehouse_id"], msg: "Warehouse not found", type: "value_error" }] } }
            : { status: 200, body: summaryBody() };
        },
        "GET /stock-movements": () => ({ status: 500, body: { detail: "Internal Server Error" } }),
      }),
    );
    renderApp("/dashboard?warehouse_id=9999");
    const u = userEvent.setup();
    const kpiError = await screen.findByText("Invalid filter: Warehouse not found");
    expect(await screen.findByText("Internal Server Error")).toBeInTheDocument();
    await u.click(within(kpiError.closest(".error-state") as HTMLElement).getByRole("button", { name: "Retry" }));
    expect(await screen.findByLabelText("Key figures")).toBeInTheDocument();
    expect(callsTo(fetchMock, "GET", "/dashboard/summary")).toHaveLength(2);
  });
});

describe("stock availability", () => {
  it("lists stock with spelled-out statuses and filters on the server", async () => {
    const fetchMock = mockApi({
      ...signedInAs("WAREHOUSE_STAFF"),
      ...lookups,
      "GET /stock-availability": () => ({
        status: 200,
        body: page([
          { ...lowRow, status: "OUT_OF_STOCK", quantity: 0 },
          lowRow,
          { ...lowRow, location: rackC, quantity: 90, status: "IN_STOCK", minimum_quantity: null },
        ]),
      }),
    });
    renderApp("/stock-availability?status=LOW_STOCK,OUT_OF_STOCK&warehouse_id=1");
    const table = await screen.findByRole("table");
    expect(await within(table).findByText("Out of stock")).toBeInTheDocument();
    expect(within(table).getByText("Low stock")).toBeInTheDocument();
    expect(within(table).getByText("In stock")).toBeInTheDocument();
    expect(within(table).getByText("0 kg")).toBeInTheDocument();
    const request = callsTo(fetchMock, "GET", "/stock-availability")[0][0];
    expect(request.searchParams.getAll("status")).toEqual(["LOW_STOCK", "OUT_OF_STOCK"]);
    expect(request.searchParams.get("warehouse_id")).toBe("1");

    await userEvent.setup().selectOptions(screen.getByLabelText("Stock status"), "OUT_OF_STOCK");
    await waitFor(() =>
      expect(callsTo(fetchMock, "GET", "/stock-availability").slice(-1)[0][0].searchParams.getAll("status")).toEqual(["OUT_OF_STOCK"]),
    );
  });

  it("shows an empty state for filters without results", async () => {
    mockApi({ ...signedInAs("WAREHOUSE_STAFF"), ...lookups, "GET /stock-availability": () => ({ status: 200, body: page([]) }) });
    renderApp("/stock-availability?category_id=1");
    expect(await screen.findByText("No stock matches these filters.")).toBeInTheDocument();
  });
});

describe("move history", () => {
  it("lists the ledger, filters by type and paginates", async () => {
    const fetchMock = mockApi({
      ...signedInAs("WAREHOUSE_STAFF"),
      ...lookups,
      "GET /stock-movements": (url) => ({
        status: 200,
        body: {
          items: [
            movement(2, { movement_type: "TRANSFER", quantity: 30, source_location_id: 10, source_location: rackA, destination_location_id: 12, destination_location: rackC, reference_type: "TRANSFER", reference_number: "TRF-000001" }),
            movement(1),
          ],
          total: 30,
          limit: 25,
          offset: Number(url.searchParams.get("offset") ?? 0),
        },
      }),
    });
    renderApp("/move-history");
    const u = userEvent.setup();
    expect(await screen.findByRole("link", { name: "TRF-000001" })).toHaveAttribute("href", "/transfers/1");
    const transferRow = screen.getByRole("link", { name: "TRF-000001" }).closest("tr")!;
    expect(within(transferRow).getByText("WH-MAIN / Rack A")).toBeInTheDocument();
    expect(within(transferRow).getByText("WH2 / Rack C")).toBeInTheDocument();
    expect(within(transferRow).getByText("Sam Staff")).toBeInTheDocument();
    expect(screen.getByText("Page 1 of 2 · 1–25 of 30")).toBeInTheDocument();

    await u.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(callsTo(fetchMock, "GET", "/stock-movements").slice(-1)[0][0].searchParams.get("offset")).toBe("25"));
    expect(await screen.findByText("Page 2 of 2 · 26–30 of 30")).toBeInTheDocument();

    await u.selectOptions(screen.getByLabelText("Movement type"), "DELIVERY");
    await waitFor(() => {
      const last = callsTo(fetchMock, "GET", "/stock-movements").slice(-1)[0][0];
      expect(last.searchParams.get("movement_type")).toBe("DELIVERY");
      expect(last.searchParams.get("offset")).toBeNull(); // filters reset to page 1
    });
  });

  it("searches by SKU and filters by location", async () => {
    const fetchMock = mockApi({ ...signedInAs("WAREHOUSE_STAFF"), ...lookups, "GET /stock-movements": () => ({ status: 200, body: page([]) }) });
    renderApp("/move-history?location_id=10");
    const u = userEvent.setup();
    expect(await screen.findByText("No movements match these filters.")).toBeInTheDocument();
    expect(callsTo(fetchMock, "GET", "/stock-movements")[0][0].searchParams.get("location_id")).toBe("10");
    await u.type(screen.getByLabelText("Search"), "STL-ROD");
    await waitFor(() => expect(callsTo(fetchMock, "GET", "/stock-movements").slice(-1)[0][0].searchParams.get("q")).toBe("STL-ROD"));
  });

  it("shows API failures with a retry", async () => {
    let fail = true;
    mockApi({
      ...signedInAs("WAREHOUSE_STAFF"),
      ...lookups,
      "GET /stock-movements": () => (fail ? { status: 500, body: { detail: "Database unavailable" } } : { status: 200, body: page([movement(1)]) }),
    });
    renderApp("/move-history");
    expect(await screen.findByText("Database unavailable")).toBeInTheDocument();
    fail = false;
    await userEvent.setup().click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("link", { name: "REC-000001" })).toBeInTheDocument();
  });
});

describe("module links", () => {
  it("opens operation lists pre-filtered from dashboard links", async () => {
    const fetchMock = mockApi({ ...signedInAs("WAREHOUSE_STAFF"), ...lookups, "GET /receipts": () => ({ status: 200, body: page([]) }) });
    renderApp("/receipts?status=READY&warehouse_id=2");
    await screen.findByText("No receipts found.");
    const request = callsTo(fetchMock, "GET", "/receipts")[0][0];
    expect(request.searchParams.getAll("status")).toEqual(["READY"]);
    expect(request.searchParams.get("warehouse_id")).toBe("2");
  });
});

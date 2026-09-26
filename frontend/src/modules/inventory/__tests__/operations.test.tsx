import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { callsTo, mockApi, page, renderApp, signedInAs } from "../../../test-utils/mockApi";
import { mainWarehouse, rackA, steelRods } from "../../master-data/__tests__/fixtures";
import { buildQuery } from "../api";
import type { InventoryDocument, StockPosition } from "../types";

const rackB = { ...rackA, id: 11, name: "Rack B", code: "RACK-B" };
const productRef = { id: 100, name: "Steel Rods", sku: "STL-ROD", is_active: true, unit_of_measure: { id: 1, name: "Piece", symbol: "pc" } };
const user = { id: 1, name: "Sam Staff" };

function doc(overrides: Partial<InventoryDocument>): InventoryDocument {
  return {
    id: 1,
    reference: "REC-000001",
    status: "DRAFT",
    scheduled_date: null,
    notes: null,
    created_by: user,
    validated_by: null,
    validated_at: null,
    canceled_at: null,
    created_at: "2026-09-26T06:00:00Z",
    updated_at: "2026-09-26T06:00:00Z",
    items: [{ id: 1, product_id: 100, product: productRef, quantity: 50 }],
    ...overrides,
  };
}

const lookups = {
  "GET /products": () => ({ status: 200, body: page([{ ...steelRods, unit_of_measure: productRef.unit_of_measure }]) }),
  "GET /locations": () => ({ status: 200, body: page([rackA, rackB]) }),
  "GET /warehouses": () => ({ status: 200, body: page([mainWarehouse]) }),
};

function stockAt(quantity: number): StockPosition[] {
  return [
    {
      id: 1,
      product_id: 100,
      product: { ...productRef, category: { id: 1, name: "Raw Materials" } },
      location_id: 10,
      location: rackA,
      quantity,
      updated_at: "2026-09-26T06:00:00Z",
    },
  ];
}

describe("receipts", () => {
  it("validates the form, creates a receipt and validates it", async () => {
    const receipt = doc({ supplier_name: "Acme Metals", supplier_reference: null, destination_location_id: 10, destination_location: rackA });
    const fetchMock = mockApi({
      ...signedInAs("WAREHOUSE_STAFF"),
      ...lookups,
      "POST /receipts": () => ({ status: 201, body: receipt }),
      "GET /receipts/1": () => ({ status: 200, body: receipt }),
      "POST /receipts/1/validate": () => ({
        status: 200,
        body: { ...receipt, status: "DONE", validated_at: "2026-09-26T07:00:00Z", validated_by: user },
      }),
      "GET /stock-movements": (url) => {
        expect(url.searchParams.get("reference_type")).toBe("RECEIPT");
        return {
          status: 200,
          body: page([
            {
              id: 9, movement_type: "RECEIPT", product_id: 100, product: productRef, quantity: 50,
              source_location_id: null, source_location: null, destination_location_id: 10, destination_location: rackA,
              reference_type: "RECEIPT", reference_id: 1, reference_number: "REC-000001", performed_by: user, created_at: "",
            },
          ]),
        };
      },
    });
    renderApp("/receipts/new");
    const u = userEvent.setup();
    await u.click(await screen.findByRole("button", { name: "Create receipt" }));
    expect(screen.getByText("Supplier is required")).toBeInTheDocument();
    expect(screen.getByText("Select a location", { selector: ".field-error" })).toBeInTheDocument();
    expect(screen.getByText("Select a product", { selector: ".field-error" })).toBeInTheDocument();
    expect(callsTo(fetchMock, "POST", "/receipts")).toHaveLength(0);

    await u.type(screen.getByLabelText("Supplier"), "Acme Metals");
    await u.selectOptions(screen.getByLabelText("Receive into"), "10");
    await u.selectOptions(screen.getByLabelText("Product for line 1"), "100");
    await u.type(screen.getByLabelText("Quantity for line 1"), "50");
    await u.click(screen.getByRole("button", { name: "Create receipt" }));

    expect(await screen.findByText("REC-000001 created.")).toBeInTheDocument();
    expect(callsTo(fetchMock, "POST", "/receipts")[0][1]).toEqual({
      supplier_name: "Acme Metals",
      supplier_reference: null,
      destination_location_id: 10,
      scheduled_date: null,
      notes: null,
      items: [{ product_id: 100, quantity: "50" }],
    });

    await u.click(screen.getByRole("button", { name: "Validate" }));
    expect(await screen.findByText("Validated. Stock has been updated.")).toBeInTheDocument();
    expect(screen.getByText("Done")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    const movements = await screen.findByRole("heading", { name: "Stock movements" });
    expect(movements).toBeInTheDocument();
    expect(screen.getAllByText("+50 pc").length).toBeGreaterThan(0);
  });

  it("lists pending receipts by default using repeated status filters", async () => {
    const fetchMock = mockApi({
      ...signedInAs("WAREHOUSE_STAFF"),
      ...lookups,
      "GET /receipts": () => ({ status: 200, body: page([doc({ supplier_name: "Acme", destination_location: rackA })]) }),
    });
    renderApp("/receipts");
    expect(await screen.findByRole("link", { name: "REC-000001" })).toBeInTheDocument();
    expect(callsTo(fetchMock, "GET", "/receipts")[0][0].searchParams.getAll("status")).toEqual(["DRAFT", "WAITING", "READY"]);
  });
});

describe("delivery orders", () => {
  const base = doc({
    reference: "DEL-000001",
    customer_name: "Globex",
    source_location_id: 10,
    source_location: rackA,
    status: "READY",
    picked_at: null,
    packed_at: null,
    items: [{ id: 1, product_id: 100, product: productRef, quantity: 10, available_quantity: 12 }],
  });

  it("walks through pick, pack and validate, showing a stock error", async () => {
    mockApi({
      ...signedInAs("WAREHOUSE_STAFF"),
      "GET /deliveries/1": () => ({ status: 200, body: base }),
      "POST /deliveries/1/pick": () => ({ status: 200, body: { ...base, picked_at: "2026-09-26T07:00:00Z", picked_by: user } }),
      "POST /deliveries/1/pack": () => ({
        status: 200,
        body: { ...base, picked_at: "2026-09-26T07:00:00Z", picked_by: user, packed_at: "2026-09-26T07:05:00Z", packed_by: user },
      }),
      "POST /deliveries/1/validate": () => ({
        status: 409,
        body: { detail: "Not enough stock: STL-ROD at WH-MAIN / Rack A (available 3, requested 10)" },
      }),
    });
    renderApp("/deliveries/1");
    const u = userEvent.setup();
    expect(await screen.findByText(/Not picked yet/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Validate" })).not.toBeInTheDocument();

    await u.click(screen.getByRole("button", { name: "Pick" }));
    expect(await screen.findByText("Items picked.")).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Pack" }));
    expect(await screen.findByText("Items packed.")).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Validate" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("available 3, requested 10");
  });

  it("warns in the form when a quantity exceeds available stock", async () => {
    mockApi({
      ...signedInAs("WAREHOUSE_STAFF"),
      ...lookups,
      "GET /stock": (url) => {
        expect(url.searchParams.get("location_id")).toBe("10");
        return { status: 200, body: page(stockAt(3)) };
      },
    });
    renderApp("/deliveries/new");
    const u = userEvent.setup();
    await u.selectOptions(await screen.findByLabelText("Ship from"), "10");
    await u.selectOptions(screen.getByLabelText("Product for line 1"), "100");
    await u.type(screen.getByLabelText("Quantity for line 1"), "5");
    expect(await screen.findByText("Only 3 pc available")).toBeInTheDocument();
  });

  it("asks before canceling", async () => {
    const fetchMock = mockApi({ ...signedInAs("WAREHOUSE_STAFF"), "GET /deliveries/1": () => ({ status: 200, body: base }) });
    vi.spyOn(window, "confirm").mockReturnValue(false);
    renderApp("/deliveries/1");
    await userEvent.setup().click(await screen.findByRole("button", { name: "Cancel" }));
    expect(callsTo(fetchMock, "POST", "/deliveries/1/cancel")).toHaveLength(0);
  });
});

describe("transfers and adjustments", () => {
  it("rejects the same source and destination", async () => {
    const fetchMock = mockApi({ ...signedInAs("WAREHOUSE_STAFF"), ...lookups, "GET /stock": () => ({ status: 200, body: page([]) }) });
    renderApp("/transfers/new");
    const u = userEvent.setup();
    await u.selectOptions(await screen.findByLabelText("From"), "10");
    await u.selectOptions(screen.getByLabelText("To"), "10");
    await u.selectOptions(screen.getByLabelText("Product for line 1"), "100");
    await u.type(screen.getByLabelText("Quantity for line 1"), "1");
    await u.click(screen.getByRole("button", { name: "Create transfer" }));
    expect(screen.getByText("Source and destination must be different locations")).toBeInTheDocument();
    expect(callsTo(fetchMock, "POST", "/transfers")).toHaveLength(0);
  });

  it("shows recorded stock and the live difference while counting", async () => {
    mockApi({ ...signedInAs("WAREHOUSE_STAFF"), ...lookups, "GET /stock": () => ({ status: 200, body: page(stockAt(100)) }) });
    renderApp("/adjustments/new");
    const u = userEvent.setup();
    await u.selectOptions(await screen.findByLabelText("Location"), "10");
    await u.selectOptions(screen.getByLabelText("Product for line 1"), "100");
    await u.type(screen.getByLabelText("Counted quantity for line 1"), "97");
    const table = screen.getByRole("table");
    expect(await within(table).findByText("100 pc")).toBeInTheDocument();
    expect(within(table).getByText("−3 pc")).toBeInTheDocument();
  });

  it("shows recorded, counted and difference on a validated adjustment", async () => {
    mockApi({
      ...signedInAs("WAREHOUSE_STAFF"),
      "GET /adjustments/1": () => ({
        status: 200,
        body: doc({
          reference: "ADJ-000001",
          status: "DONE",
          location_id: 10,
          location: rackA,
          reason: "Damaged",
          items: [{ id: 1, product_id: 100, product: productRef, counted_quantity: 97, recorded_quantity: 100, difference: -3 }],
        }),
      }),
      "GET /stock-movements": () => ({ status: 200, body: page([]) }),
    });
    renderApp("/adjustments/1");
    const row = (await screen.findByRole("link", { name: "Steel Rods" })).closest("tr")!;
    expect(within(row).getByText("100 pc")).toBeInTheDocument();
    expect(within(row).getByText("97 pc")).toBeInTheDocument();
    expect(within(row).getByText("−3 pc")).toBeInTheDocument();
  });
});

describe("stock", () => {
  it("sends the old /stock URL to Stock Availability", async () => {
    mockApi({
      ...signedInAs("WAREHOUSE_STAFF"),
      ...lookups,
      "GET /categories": () => ({ status: 200, body: page([]) }),
      "GET /stock-availability": () => ({ status: 200, body: page([]) }),
    });
    renderApp("/stock");
    expect(await screen.findByRole("heading", { name: "Stock Availability" })).toBeInTheDocument();
  });

  it("shows stock by location on the product page", async () => {
    mockApi({
      ...signedInAs("WAREHOUSE_STAFF"),
      "GET /products/100": () => ({ status: 200, body: steelRods }),
      "GET /reorder-rules": () => ({ status: 200, body: page([]) }),
      "GET /stock/products/100": () => ({
        status: 200,
        body: { product: { ...productRef, category: { id: 1, name: "Raw" } }, total_quantity: 120, locations: [
          { location: rackA, quantity: 70 },
          { location: rackB, quantity: 50 },
        ] },
      }),
    });
    renderApp("/products/100");
    const panel = await screen.findByRole("region", { name: "Stock by location" });
    await waitFor(() => expect(within(panel).getByText("120 pc")).toBeInTheDocument());
    expect(within(panel).getByText("WH-MAIN / Rack B")).toBeInTheDocument();
  });

  it("builds repeated query parameters", () => {
    expect(buildQuery({ status: ["DRAFT", "READY"], q: "", warehouse_id: 2 })).toBe("?status=DRAFT&status=READY&warehouse_id=2");
  });
});

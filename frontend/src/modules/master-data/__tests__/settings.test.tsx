import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { callsTo, mockApi, page, renderApp, signedInAs } from "../../../test-utils/mockApi";
import { kilogram, mainWarehouse, rackA, rawMaterials, steelRods, steelRule } from "./fixtures";

describe("categories", () => {
  it("creates a category and reloads the list", async () => {
    let categories = [rawMaterials];
    const fetchMock = mockApi({
      ...signedInAs("INVENTORY_MANAGER"),
      "GET /categories": () => ({ status: 200, body: page(categories) }),
      "POST /categories": (_, body) => {
        const created = { ...rawMaterials, id: 3, ...(body as object) };
        categories = [...categories, created];
        return { status: 201, body: created };
      },
    });
    renderApp("/categories");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "New category" }));
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(screen.getByText("Name is required")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Name"), "Packaging");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Category created.")).toBeInTheDocument();
    expect(await screen.findByRole("cell", { name: "Packaging" })).toBeInTheDocument();
    expect(callsTo(fetchMock, "POST", "/categories")[0][1]).toEqual({ name: "Packaging", description: null, is_active: true });
  });

  it("deactivates a category", async () => {
    const fetchMock = mockApi({
      ...signedInAs("INVENTORY_MANAGER"),
      "GET /categories": () => ({ status: 200, body: page([rawMaterials]) }),
      "PATCH /categories/1": () => ({ status: 200, body: { ...rawMaterials, is_active: false } }),
    });
    renderApp("/categories");
    await userEvent.setup().click(await screen.findByRole("button", { name: "Deactivate" }));
    expect(await screen.findByText("Category deactivated.")).toBeInTheDocument();
    expect(callsTo(fetchMock, "PATCH", "/categories/1")[0][1]).toEqual({ is_active: false });
  });

  it("is read-only for warehouse staff", async () => {
    mockApi({ ...signedInAs("WAREHOUSE_STAFF"), "GET /categories": () => ({ status: 200, body: page([rawMaterials]) }) });
    renderApp("/categories");
    expect(await screen.findByRole("cell", { name: "Raw Materials" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "New category" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
  });
});

describe("units of measure", () => {
  it("shows a duplicate-symbol error from the API", async () => {
    mockApi({
      ...signedInAs("INVENTORY_MANAGER"),
      "GET /units": () => ({ status: 200, body: page([kilogram]) }),
      "POST /units": () => ({
        status: 409,
        body: { detail: [{ loc: ["body", "symbol"], msg: "A unit with this symbol already exists", type: "value_error" }] },
      }),
    });
    renderApp("/units");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "New unit" }));
    await user.type(screen.getByLabelText("Name"), "Kilo");
    await user.type(screen.getByLabelText("Symbol"), "kg");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("A unit with this symbol already exists")).toBeInTheDocument();
  });
});

describe("warehouses and locations", () => {
  it("validates the warehouse code", async () => {
    const fetchMock = mockApi({
      ...signedInAs("INVENTORY_MANAGER"),
      "GET /warehouses": () => ({ status: 200, body: page([mainWarehouse]) }),
    });
    renderApp("/warehouses");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "New warehouse" }));
    await user.type(screen.getByLabelText("Name"), "Overflow");
    await user.type(screen.getByLabelText("Code"), "has space");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(screen.getByText(/letters, numbers/)).toBeInTheDocument();
    expect(callsTo(fetchMock, "POST", "/warehouses")).toHaveLength(0);
  });

  it("adds a location inside a warehouse", async () => {
    let locations = [rackA];
    const fetchMock = mockApi({
      ...signedInAs("INVENTORY_MANAGER"),
      "GET /warehouses/1": () => ({ status: 200, body: mainWarehouse }),
      "GET /locations": (url) => {
        expect(url.searchParams.get("warehouse_id")).toBe("1");
        return { status: 200, body: page(locations) };
      },
      "POST /locations": (_, body) => {
        const created = { ...rackA, id: 11, ...(body as object), code: "RACK-B" };
        locations = [...locations, created];
        return { status: 201, body: created };
      },
    });
    renderApp("/warehouses/1");
    const user = userEvent.setup();
    expect(await screen.findByRole("heading", { name: "Main Warehouse" })).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "New location" }));
    // The warehouse is fixed by the page, so it is not asked for.
    expect(screen.queryByLabelText("Warehouse")).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("Name"), "Rack B");
    await user.type(screen.getByLabelText("Code"), "rack-b");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Location created.")).toBeInTheDocument();
    expect(await screen.findByRole("cell", { name: "RACK-B" })).toBeInTheDocument();
    expect(callsTo(fetchMock, "POST", "/locations")[0][1]).toEqual({
      warehouse_id: 1,
      name: "Rack B",
      code: "rack-b",
      is_active: true,
    });
  });

  it("requires a warehouse when adding from the Locations page", async () => {
    mockApi({
      ...signedInAs("INVENTORY_MANAGER"),
      "GET /warehouses": () => ({ status: 200, body: page([mainWarehouse]) }),
      "GET /locations": () => ({ status: 200, body: page([rackA]) }),
    });
    renderApp("/locations");
    const user = userEvent.setup();
    expect(await screen.findByRole("link", { name: "Main Warehouse" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "New location" }));
    await user.type(screen.getByLabelText("Name"), "Rack C");
    await user.type(screen.getByLabelText("Code"), "C");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(screen.getByText("Select a warehouse", { selector: ".field-error" })).toBeInTheDocument();
  });
});

describe("reorder rules", () => {
  const routes = {
    "GET /products": () => ({ status: 200, body: page([steelRods]) }),
    "GET /warehouses": () => ({ status: 200, body: page([mainWarehouse]) }),
    "GET /locations": () => ({ status: 200, body: page([rackA]) }),
  };

  it("rejects a target below the minimum and creates a valid rule", async () => {
    const fetchMock = mockApi({
      ...signedInAs("INVENTORY_MANAGER"),
      ...routes,
      "GET /reorder-rules": () => ({ status: 200, body: page([]) }),
      "POST /reorder-rules": () => ({ status: 201, body: steelRule }),
    });
    renderApp("/reorder-rules?product_id=100");
    const user = userEvent.setup();
    await screen.findByRole("option", { name: "Steel Rods (STL-ROD)", hidden: true });
    await user.click(screen.getByRole("button", { name: "New rule" }));

    const form = screen.getByRole("form", { name: "reorder rule form" });
    // Product is pre-selected from the ?product_id= filter.
    expect(within(form).getByLabelText("Product")).toHaveValue("100");
    await user.selectOptions(within(form).getByLabelText("Location"), "10");
    await user.type(within(form).getByLabelText("Minimum quantity"), "50");
    await user.type(within(form).getByLabelText("Target quantity"), "10");
    await user.click(within(form).getByRole("button", { name: "Save" }));
    expect(within(form).getByText("Target quantity must be greater than or equal to the minimum quantity")).toBeInTheDocument();
    expect(callsTo(fetchMock, "POST", "/reorder-rules")).toHaveLength(0);

    await user.clear(within(form).getByLabelText("Target quantity"));
    await user.type(within(form).getByLabelText("Target quantity"), "80");
    await user.click(within(form).getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Reorder rule created.")).toBeInTheDocument();
    expect(callsTo(fetchMock, "POST", "/reorder-rules")[0][1]).toEqual({
      product_id: 100,
      location_id: 10,
      minimum_quantity: "50",
      target_quantity: "80",
      is_active: true,
    });
    await waitFor(() =>
      expect(callsTo(fetchMock, "GET", "/reorder-rules").every(([url]) => url.searchParams.get("product_id") === "100")).toBe(true),
    );
  });

  it("lists rules with product and location", async () => {
    mockApi({ ...signedInAs("WAREHOUSE_STAFF"), ...routes, "GET /reorder-rules": () => ({ status: 200, body: page([steelRule]) }) });
    renderApp("/reorder-rules");
    expect(await screen.findByRole("link", { name: "Steel Rods" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "WH-MAIN / Rack A" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "New rule" })).not.toBeInTheDocument();
  });
});

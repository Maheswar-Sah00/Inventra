import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { callsTo, mockApi, page, renderApp, signedInAs } from "../../../test-utils/mockApi";
import { finishedGoods, kilogram, rackA, rawMaterials, steelRods } from "./fixtures";

const lookups = {
  "GET /categories": () => ({ status: 200, body: page([rawMaterials, finishedGoods]) }),
  "GET /units": () => ({ status: 200, body: page([kilogram]) }),
  "GET /locations": () => ({ status: 200, body: page([rackA]) }),
};

describe("products list", () => {
  it("lists products and searches by name or SKU on the server", async () => {
    const fetchMock = mockApi({
      ...signedInAs("WAREHOUSE_STAFF"),
      ...lookups,
      "GET /products": (url) => ({
        status: 200,
        body: page(url.searchParams.get("q") === "stl" ? [steelRods] : [steelRods, { ...steelRods, id: 101, name: "Chair", sku: "CHR-1" }]),
      }),
    });
    renderApp("/products");

    expect(await screen.findByRole("link", { name: "Chair" })).toBeInTheDocument();
    expect(screen.getByText("STL-ROD")).toBeInTheDocument();
    // Staff can browse but not create.
    expect(screen.queryByRole("button", { name: "New product" })).not.toBeInTheDocument();

    await userEvent.setup().type(screen.getByLabelText("Search"), "stl");
    await waitFor(() => expect(screen.queryByRole("link", { name: "Chair" })).not.toBeInTheDocument());
    const lastQuery = callsTo(fetchMock, "GET", "/products").slice(-1)[0][0];
    expect(lastQuery.searchParams.get("q")).toBe("stl");
    expect(lastQuery.searchParams.get("is_active")).toBe("true");
  });

  it("filters by category", async () => {
    const fetchMock = mockApi({
      ...signedInAs("INVENTORY_MANAGER"),
      ...lookups,
      "GET /products": () => ({ status: 200, body: page([steelRods]) }),
    });
    renderApp("/products");
    const user = userEvent.setup();
    await screen.findByRole("option", { name: "Finished Goods" });
    await user.selectOptions(screen.getByLabelText("Category"), "2");
    await waitFor(() =>
      expect(callsTo(fetchMock, "GET", "/products").slice(-1)[0][0].searchParams.get("category_id")).toBe("2"),
    );
    expect(screen.getByRole("button", { name: "New product" })).toBeInTheDocument();
  });
});

describe("product form", () => {
  it("validates before submitting", async () => {
    const fetchMock = mockApi({ ...signedInAs("INVENTORY_MANAGER"), ...lookups });
    renderApp("/products/new");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Create product" }));

    expect(screen.getByText("Name is required")).toBeInTheDocument();
    expect(screen.getByText("SKU is required")).toBeInTheDocument();
    expect(screen.getByText("Select a category", { selector: ".field-error" })).toBeInTheDocument();
    expect(screen.getByText("Select a unit of measure", { selector: ".field-error" })).toBeInTheDocument();

    await user.type(screen.getByLabelText("Initial stock (optional)"), "-5");
    await user.click(screen.getByRole("button", { name: "Create product" }));
    expect(screen.getByText("Initial stock cannot be negative")).toBeInTheDocument();
    expect(callsTo(fetchMock, "POST", "/products")).toHaveLength(0);
  });

  it("asks for a location when initial stock is entered and creates the product", async () => {
    const fetchMock = mockApi({
      ...signedInAs("INVENTORY_MANAGER"),
      ...lookups,
      "POST /products": () => ({ status: 201, body: { ...steelRods, initial_stock: 40, initial_location_id: 10, initial_location: rackA } }),
      "GET /products/100": () => ({ status: 200, body: { ...steelRods, initial_stock: 40, initial_location_id: 10, initial_location: rackA } }),
      "GET /reorder-rules": () => ({ status: 200, body: page([]) }),
    });
    renderApp("/products/new");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Name"), "Steel Rods");
    await user.type(screen.getByLabelText("SKU / Code"), "stl-rod");
    await user.selectOptions(screen.getByLabelText("Category"), "1");
    await user.selectOptions(screen.getByLabelText("Unit of measure"), "1");
    await user.type(screen.getByLabelText("Initial stock (optional)"), "40");

    await user.click(screen.getByRole("button", { name: "Create product" }));
    expect(screen.getByText("Select a location for the initial stock", { selector: ".field-error" })).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Initial stock location"), "10");
    await user.click(screen.getByRole("button", { name: "Create product" }));

    expect(await screen.findByText("Product created.")).toBeInTheDocument();
    expect(screen.getByText("40 kg at WH-MAIN / Rack A")).toBeInTheDocument();
    expect(callsTo(fetchMock, "POST", "/products")[0][1]).toEqual({
      name: "Steel Rods",
      sku: "stl-rod",
      category_id: 1,
      unit_of_measure_id: 1,
      initial_stock: "40",
      initial_location_id: 10,
    });
  });

  it("shows a duplicate-SKU error from the API next to the SKU field", async () => {
    mockApi({
      ...signedInAs("INVENTORY_MANAGER"),
      ...lookups,
      "POST /products": () => ({
        status: 409,
        body: { detail: [{ loc: ["body", "sku"], msg: "A product with this SKU already exists", type: "value_error" }] },
      }),
    });
    renderApp("/products/new");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Name"), "Steel Rods");
    await user.type(screen.getByLabelText("SKU / Code"), "STL-ROD");
    await user.selectOptions(screen.getByLabelText("Category"), "1");
    await user.selectOptions(screen.getByLabelText("Unit of measure"), "1");
    await user.click(screen.getByRole("button", { name: "Create product" }));

    expect(await screen.findByText("A product with this SKU already exists")).toBeInTheDocument();
    expect(screen.getByLabelText("SKU / Code")).toHaveAttribute("aria-invalid", "true");
  });

  it("is only available to inventory managers", async () => {
    mockApi({ ...signedInAs("WAREHOUSE_STAFF") });
    renderApp("/products/new");
    expect(await screen.findByRole("heading", { name: "Inventory Dashboard" })).toBeInTheDocument();
  });

  it("edits an existing product without initial stock fields", async () => {
    const fetchMock = mockApi({
      ...signedInAs("INVENTORY_MANAGER"),
      ...lookups,
      "GET /products/100": () => ({ status: 200, body: steelRods }),
      "PATCH /products/100": (_, body) => ({ status: 200, body: { ...steelRods, ...(body as object) } }),
      "GET /reorder-rules": () => ({ status: 200, body: page([]) }),
    });
    renderApp("/products/100/edit");
    const user = userEvent.setup();
    const name = await screen.findByLabelText("Name");
    await waitFor(() => expect(name).toHaveValue("Steel Rods"));
    expect(screen.queryByLabelText("Initial stock (optional)")).not.toBeInTheDocument();

    await user.clear(name);
    await user.type(name, "Steel Rods 12mm");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByText("Product updated.")).toBeInTheDocument();
    expect(callsTo(fetchMock, "PATCH", "/products/100")[0][1]).toMatchObject({ name: "Steel Rods 12mm", is_active: true });
  });
});

describe("product detail", () => {
  it("shows details and reorder rules", async () => {
    mockApi({
      ...signedInAs("WAREHOUSE_STAFF"),
      "GET /products/100": () => ({ status: 200, body: steelRods }),
      "GET /reorder-rules": (url) => {
        expect(url.searchParams.get("product_id")).toBe("100");
        return {
          status: 200,
          body: page([
            {
              id: 1,
              product_id: 100,
              product: { id: 100, name: "Steel Rods", sku: "STL-ROD", is_active: true },
              location_id: 10,
              location: rackA,
              minimum_quantity: 10,
              target_quantity: 50,
              is_active: true,
              created_at: "",
              updated_at: "",
            },
          ]),
        };
      },
    });
    renderApp("/products/100");
    expect(await screen.findByRole("heading", { name: "Steel Rods" })).toBeInTheDocument();
    expect(screen.getByText("Kilogram (kg)")).toBeInTheDocument();
    const rules = screen.getByRole("table");
    expect(within(rules).getByText("WH-MAIN / Rack A")).toBeInTheDocument();
    expect(within(rules).getByText("50")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
  });
});

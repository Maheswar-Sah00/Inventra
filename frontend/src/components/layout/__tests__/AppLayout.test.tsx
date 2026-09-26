import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { mockApi, page, renderApp, signedInAs } from "../../../test-utils/mockApi";

describe("app layout", () => {
  it("groups navigation as in the brief", async () => {
    mockApi({ ...signedInAs("WAREHOUSE_STAFF"), "GET /products": () => ({ status: 200, body: page([]) }), "GET /categories": () => ({ status: 200, body: page([]) }) });
    renderApp("/products");
    const nav = await screen.findByRole("navigation", { name: "Main" });
    expect(within(nav).getByText("Operations")).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Move History" })).toHaveAttribute("href", "/move-history");
    expect(within(nav).getByRole("link", { name: "Warehouses" })).toHaveAttribute("href", "/warehouses");
  });

  it("toggles the small-screen menu and closes it after navigating", async () => {
    mockApi({
      ...signedInAs("WAREHOUSE_STAFF"),
      "GET /products": () => ({ status: 200, body: page([]) }),
      "GET /categories": () => ({ status: 200, body: page([]) }),
    });
    renderApp("/products");
    const user = userEvent.setup();
    const toggle = await screen.findByRole("button", { name: "Menu" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await user.click(toggle);
    expect(screen.getByRole("button", { name: "Close" })).toHaveAttribute("aria-expanded", "true");
    await user.click(within(screen.getByRole("navigation", { name: "Main" })).getByRole("link", { name: "Categories" }));
    expect(await screen.findByRole("button", { name: "Menu" })).toHaveAttribute("aria-expanded", "false");
  });
});

describe("api errors", () => {
  it("never shows raw server errors", async () => {
    mockApi({
      ...signedInAs("WAREHOUSE_STAFF"),
      "GET /products": () => ({ status: 500, body: { detail: "Traceback (most recent call last): sqlalchemy.exc.OperationalError" } }),
      "GET /categories": () => ({ status: 200, body: page([]) }),
    });
    renderApp("/products");
    expect(await screen.findByText("The server ran into a problem. Please try again.")).toBeInTheDocument();
    expect(screen.queryByText(/Traceback|sqlalchemy/)).not.toBeInTheDocument();
  });
});

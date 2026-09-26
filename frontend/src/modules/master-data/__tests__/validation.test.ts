import { describe, expect, it } from "vitest";

import { toQuery } from "../api";
import { requiredSelection, requiredText, validateCode, validateQuantity, validateTarget } from "../validation";

describe("master data validation", () => {
  it("requires text", () => {
    expect(requiredText("  ", "Name")).toBe("Name is required");
    expect(requiredText("x".repeat(101), "Name")).toMatch(/at most 100/);
    expect(requiredText("Rack A", "Name")).toBeNull();
  });

  it("validates codes and SKUs", () => {
    expect(validateCode("", "SKU")).toBe("SKU is required");
    expect(validateCode("has space")).toMatch(/letters, numbers/);
    expect(validateCode("-A")).toMatch(/starting with/);
    expect(validateCode("x".repeat(33))).toMatch(/at most 32/);
    expect(validateCode("stl-rod_10/a.b", "SKU", 64)).toBeNull();
  });

  it("requires selections", () => {
    expect(requiredSelection("", "category")).toBe("Select a category");
    expect(requiredSelection("3", "category")).toBeNull();
  });

  it("validates quantities", () => {
    expect(validateQuantity("", "Initial stock", { optional: true })).toBeNull();
    expect(validateQuantity("", "Minimum quantity")).toMatch(/required/);
    expect(validateQuantity("-1", "Initial stock")).toMatch(/negative/);
    expect(validateQuantity("1.2345", "Initial stock")).toMatch(/3 decimals/);
    expect(validateQuantity("abc", "Initial stock")).toMatch(/number/);
    expect(validateQuantity("100000000000", "Initial stock")).toMatch(/too large/);
    expect(validateQuantity("12.5", "Initial stock")).toBeNull();
  });

  it("requires target >= minimum", () => {
    expect(validateTarget("10", "5")).toMatch(/greater than or equal/);
    expect(validateTarget("10", "10")).toBeNull();
    expect(validateTarget("10", "")).toMatch(/required/);
  });

  it("builds query strings without empty values", () => {
    expect(toQuery({ q: "steel", category_id: "", is_active: undefined, limit: 20 })).toBe("?q=steel&limit=20");
    expect(toQuery({})).toBe("");
  });
});

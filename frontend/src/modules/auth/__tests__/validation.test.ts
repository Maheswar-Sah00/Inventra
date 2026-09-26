import { describe, expect, it } from "vitest";

import {
  collectErrors,
  validateEmail,
  validateName,
  validateOtp,
  validatePassword,
  validatePasswordConfirmation,
} from "../validation";

describe("auth validation", () => {
  it("validates email", () => {
    expect(validateEmail("")).toBe("Email is required");
    expect(validateEmail("nope")).toBe("Enter a valid email address");
    expect(validateEmail(" user@example.com ")).toBeNull();
  });

  it("validates name", () => {
    expect(validateName("  ")).toBe("Name is required");
    expect(validateName("A")).toMatch(/at least 2/);
    expect(validateName("Asha Rao")).toBeNull();
  });

  it("enforces the same password rules as the API", () => {
    expect(validatePassword("")).toBe("Password is required");
    expect(validatePassword("short1")).toMatch(/at least 8/);
    expect(validatePassword("allletters")).toMatch(/letter and one number/);
    expect(validatePassword("12345678")).toMatch(/letter and one number/);
    expect(validatePassword(" Secret123")).toMatch(/space/);
    expect(validatePassword("Secret123")).toBeNull();
  });

  it("checks password confirmation", () => {
    expect(validatePasswordConfirmation("Secret123", "")).toMatch(/confirm/);
    expect(validatePasswordConfirmation("Secret123", "Secret124")).toBe("Passwords do not match");
    expect(validatePasswordConfirmation("Secret123", "Secret123")).toBeNull();
  });

  it("validates OTP format", () => {
    expect(validateOtp("")).toMatch(/Enter/);
    expect(validateOtp("12a456")).toMatch(/6 digits/);
    expect(validateOtp("12345")).toMatch(/6 digits/);
    expect(validateOtp("123456")).toBeNull();
  });

  it("collects only real errors", () => {
    expect(collectErrors({ a: null, b: "bad" })).toEqual({ b: "bad" });
  });
});

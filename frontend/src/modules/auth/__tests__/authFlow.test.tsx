import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AppRoutes } from "../../../App";
import { AuthProvider } from "../AuthContext";
import { tokenStorage } from "../tokenStorage";
import type { User } from "../types";

const USER: User = {
  id: 1,
  name: "Asha Rao",
  email: "asha@example.com",
  role: "INVENTORY_MANAGER",
  is_active: true,
  created_at: "2026-09-26T05:00:00+00:00",
  updated_at: "2026-09-26T05:00:00+00:00",
};

type Handler = (init: RequestInit | undefined) => { status: number; body?: unknown };

/** Minimal fetch stub keyed by "METHOD /path". */
function mockApi(routes: Record<string, Handler>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const key = `${init?.method ?? "GET"} ${url.replace(/^\/api/, "")}`;
    const handler = routes[key];
    if (!handler) throw new Error(`Unexpected request: ${key}`);
    const { status, body } = handler(init);
    return new Response(body === undefined ? "" : JSON.stringify(body), { status });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function renderApp(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("route protection", () => {
  it("redirects unauthenticated visitors from a protected page to login", async () => {
    mockApi({});
    renderApp("/profile");
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  it("redirects an authenticated user away from /login to the dashboard", async () => {
    tokenStorage.save("valid-token", 3600);
    mockApi({ "GET /auth/me": () => ({ status: 200, body: USER }) });
    renderApp("/login");
    expect(await screen.findByRole("heading", { name: "Inventory Dashboard" })).toBeInTheDocument();
  });

  it("clears a stale token that the API rejects", async () => {
    tokenStorage.save("revoked-token", 3600);
    mockApi({ "GET /auth/me": () => ({ status: 401, body: { detail: "Invalid or expired token" } }) });
    renderApp("/dashboard");
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(tokenStorage.getToken()).toBeNull();
  });
});

describe("login", () => {
  it("signs in, stores the token and lands on the dashboard", async () => {
    const fetchMock = mockApi({
      "POST /auth/login": () => ({
        status: 200,
        body: { access_token: "new-token", token_type: "bearer", expires_in: 3600, user: USER },
      }),
    });
    renderApp("/login");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Email"), "asha@example.com");
    await user.type(screen.getByLabelText("Password"), "Secret123");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("heading", { name: "Inventory Dashboard" })).toBeInTheDocument();
    expect(tokenStorage.getToken()).toBe("new-token");
    expect(JSON.parse(fetchMock.mock.calls[0][1]!.body as string)).toEqual({
      email: "asha@example.com",
      password: "Secret123",
    });
  });

  it("shows the API error for bad credentials", async () => {
    mockApi({ "POST /auth/login": () => ({ status: 401, body: { detail: "Invalid email or password" } }) });
    renderApp("/login");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Email"), "asha@example.com");
    await user.type(screen.getByLabelText("Password"), "Wrong1234");
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password");
    expect(tokenStorage.getToken()).toBeNull();
  });

  it("validates fields before calling the API", async () => {
    const fetchMock = mockApi({});
    renderApp("/login");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Sign in" }));
    expect(screen.getByText("Email is required")).toBeInTheDocument();
    expect(screen.getByText("Password is required")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("fills the form with the demo account shown in development", async () => {
    mockApi({});
    renderApp("/login");
    const user = userEvent.setup();
    expect(await screen.findByText("admin@stocksense.com")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Use demo account" }));
    expect(screen.getByLabelText("Email")).toHaveValue("admin@stocksense.com");
    expect(screen.getByLabelText("Password")).toHaveValue("Admin1234");
  });
});

describe("logout", () => {
  it("revokes the session, clears the token and returns to login", async () => {
    tokenStorage.save("valid-token", 3600);
    const fetchMock = mockApi({
      "GET /auth/me": () => ({ status: 200, body: USER }),
      "POST /auth/logout": () => ({ status: 200, body: { message: "Logged out" } }),
    });
    renderApp("/dashboard");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Logout" }));

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(tokenStorage.getToken()).toBeNull();
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/logout", expect.objectContaining({ method: "POST" }));
  });
});

describe("profile", () => {
  it("shows the user's profile details and saves a new name", async () => {
    tokenStorage.save("valid-token", 3600);
    mockApi({
      "GET /auth/me": () => ({ status: 200, body: USER }),
      "PATCH /users/me": (init) => ({
        status: 200,
        body: { ...USER, name: JSON.parse(init!.body as string).name },
      }),
    });
    renderApp("/profile");
    expect(await screen.findByRole("heading", { name: "My Profile" })).toBeInTheDocument();
    expect(screen.getByText("asha@example.com")).toBeInTheDocument();
    expect(screen.getAllByText("Inventory Manager").length).toBeGreaterThan(0);
    expect(screen.getByText("Active")).toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Edit name" }));
    const input = screen.getByLabelText("Full name");
    await user.clear(input);
    await user.type(input, "Asha K Rao");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByText("Profile updated.")).toBeInTheDocument();
    expect(screen.getAllByText("Asha K Rao").length).toBeGreaterThan(0);
  });
});

describe("password reset", () => {
  it("requests an OTP, verifies it and sets a new password", async () => {
    mockApi({
      "POST /auth/forgot-password": () => ({ status: 202, body: { message: "If an account exists…" } }),
      "POST /auth/verify-otp": () => ({ status: 200, body: { reset_token: "reset-token", expires_in: 600 } }),
      "POST /auth/reset-password": (init) => {
        expect(JSON.parse(init!.body as string)).toEqual({
          reset_token: "reset-token",
          password: "BrandNew456",
          confirm_password: "BrandNew456",
        });
        return { status: 200, body: { message: "Your password has been reset. You can now sign in." } };
      },
    });
    renderApp("/forgot-password");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Email"), "asha@example.com");
    await user.click(screen.getByRole("button", { name: "Send verification code" }));

    await user.type(await screen.findByLabelText("Verification code"), "123456");
    await user.click(screen.getByRole("button", { name: "Verify code" }));

    await user.type(await screen.findByLabelText("New password"), "BrandNew456");
    await user.type(screen.getByLabelText("Confirm new password"), "BrandNew456");
    await user.click(screen.getByRole("button", { name: "Reset password" }));

    await waitFor(() => expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument());
    expect(screen.getByText("Your password has been reset. You can now sign in.")).toBeInTheDocument();
  });

  it("shows an error for an invalid code", async () => {
    mockApi({
      "POST /auth/verify-otp": () => ({ status: 400, body: { detail: "Invalid or expired verification code" } }),
    });
    renderApp("/reset-password?email=asha%40example.com");
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Verification code"), "000000");
    await user.click(screen.getByRole("button", { name: "Verify code" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid or expired verification code");
  });
});

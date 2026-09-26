import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { AppRoutes } from "../App";
import { AuthProvider } from "../modules/auth";
import { tokenStorage } from "../modules/auth/tokenStorage";
import type { User, UserRole } from "../modules/auth/types";

export type MockResponse = { status: number; body?: unknown };
export type MockHandler = (url: URL, body: unknown) => MockResponse;

/**
 * Stubs fetch. Routes are keyed "METHOD /path" (without the /api prefix and query string).
 * Returns the mock so tests can inspect calls, plus a helper listing request URLs for a route.
 */
export function mockApi(routes: Record<string, MockHandler>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(typeof input === "string" ? input : input.toString(), "http://localhost");
    const key = `${init?.method ?? "GET"} ${url.pathname.replace(/^\/api/, "")}`;
    const handler = routes[key];
    if (!handler) throw new Error(`Unexpected request: ${key}${url.search}`);
    const body = init?.body ? JSON.parse(init.body as string) : undefined;
    const { status, body: responseBody } = handler(url, body);
    return new Response(responseBody === undefined ? "" : JSON.stringify(responseBody), { status });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

/** Requests made to `METHOD /path`, as [URL, parsed JSON body] pairs. */
export function callsTo(fetchMock: ReturnType<typeof mockApi>, method: string, path: string) {
  return fetchMock.mock.calls
    .map(([input, init]) => [new URL(String(input), "http://localhost"), init as RequestInit | undefined] as const)
    .filter(([url, init]) => (init?.method ?? "GET") === method && url.pathname === `/api${path}`)
    .map(([url, init]) => [url, init?.body ? JSON.parse(init.body as string) : undefined] as const);
}

export const page = <T,>(items: T[], total = items.length) => ({ items, total, limit: 20, offset: 0 });

export function makeUser(role: UserRole): User {
  return {
    id: 1,
    name: role === "INVENTORY_MANAGER" ? "Maya Manager" : "Sam Staff",
    email: "user@example.com",
    role,
    is_active: true,
    created_at: "2026-09-26T05:00:00Z",
    updated_at: "2026-09-26T05:00:00Z",
  };
}

/** Handler for GET /auth/me returning a signed-in user with `role`. Also stores a token. */
export function signedInAs(role: UserRole): Record<string, MockHandler> {
  tokenStorage.save("test-token", 3600);
  return { "GET /auth/me": () => ({ status: 200, body: makeUser(role) }) };
}

export function renderApp(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </MemoryRouter>,
  );
}

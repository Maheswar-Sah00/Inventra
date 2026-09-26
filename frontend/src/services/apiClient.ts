/**
 * Shared HTTP client for the StockSense API.
 *
 * - Prefixes paths with VITE_API_BASE_URL (default "/api").
 * - Attaches the signed-in user's bearer token automatically.
 * - Turns FastAPI error payloads into an ApiError with a readable message and per-field errors.
 * - When an authenticated request gets 401, notifies the auth module so the session is cleared.
 */
import { tokenStorage } from "../modules/auth/tokenStorage";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly fieldErrors: Record<string, string> = {},
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type RequestOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  /** Send the stored access token (default true). */
  auth?: boolean;
  signal?: AbortSignal;
};

let unauthorizedHandler: (() => void) | null = null;

/** Registered by AuthProvider; called when the API rejects our token. */
export function setUnauthorizedHandler(handler: (() => void) | null) {
  unauthorizedHandler = handler;
}

type ValidationIssue = { loc?: (string | number)[]; msg?: string };

function cleanMessage(msg: string) {
  return msg.replace(/^Value error, /, "");
}

function parseError(status: number, payload: unknown): ApiError {
  // Never surface server internals (e.g. "Internal Server Error", stack traces) to users.
  if (status === 502 || status === 503 || status === 504) {
    return new ApiError("The server is not reachable right now. Please try again in a moment.", status);
  }
  if (status >= 500) return new ApiError("The server ran into a problem. Please try again.", status);
  const detail = (payload as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return new ApiError(detail, status);
  if (Array.isArray(detail)) {
    const fieldErrors: Record<string, string> = {};
    const general: string[] = [];
    for (const issue of detail as ValidationIssue[]) {
      const msg = cleanMessage(issue.msg ?? "Invalid value");
      const loc = issue.loc ?? [];
      const field = loc.length > 1 ? String(loc[loc.length - 1]) : null;
      if (field && !(field in fieldErrors)) fieldErrors[field] = msg;
      else if (!field) general.push(msg);
    }
    return new ApiError(general[0] ?? "Please correct the highlighted fields.", status, fieldErrors);
  }
  if (status === 429) return new ApiError("Too many requests. Please wait a moment and try again.", status);
  return new ApiError("Something went wrong. Please try again.", status);
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = true, signal } = options;
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = auth ? tokenStorage.getToken() : null;
  if (token) headers.Authorization = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (error) {
    if ((error as Error).name === "AbortError") throw error;
    throw new ApiError("Cannot reach the server. Check your connection and try again.", 0);
  }

  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    if (response.status === 401 && token) unauthorizedHandler?.();
    throw parseError(response.status, payload);
  }
  return payload as T;
}

/**
 * Persists the access token so a page refresh keeps the user signed in.
 * The token is short-lived and revoked server-side on logout; nothing else sensitive is stored.
 */
const TOKEN_KEY = "stocksense.auth.token";
const EXPIRES_KEY = "stocksense.auth.expiresAt";

function safeStorage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export const tokenStorage = {
  TOKEN_KEY,

  getToken(): string | null {
    const storage = safeStorage();
    const token = storage?.getItem(TOKEN_KEY) ?? null;
    const expiresAt = Number(storage?.getItem(EXPIRES_KEY) ?? 0);
    if (!token) return null;
    if (expiresAt && Date.now() >= expiresAt) {
      this.clear();
      return null;
    }
    return token;
  },

  getExpiresAt(): number | null {
    const value = Number(safeStorage()?.getItem(EXPIRES_KEY) ?? 0);
    return value || null;
  },

  save(token: string, expiresInSeconds: number) {
    const storage = safeStorage();
    storage?.setItem(TOKEN_KEY, token);
    storage?.setItem(EXPIRES_KEY, String(Date.now() + expiresInSeconds * 1000));
  },

  clear() {
    const storage = safeStorage();
    storage?.removeItem(TOKEN_KEY);
    storage?.removeItem(EXPIRES_KEY);
  },
};

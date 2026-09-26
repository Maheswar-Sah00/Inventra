import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { setUnauthorizedHandler } from "../../services/apiClient";
import { authApi } from "./authApi";
import { tokenStorage } from "./tokenStorage";
import type { SignupPayload, User, UserRole } from "./types";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

export type AuthContextValue = {
  status: AuthStatus;
  user: User | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<User>;
  signup: (payload: SignupPayload) => Promise<User>;
  logout: () => Promise<void>;
  /** Replace the cached user after a profile update. */
  setUser: (user: User) => void;
  hasRole: (...roles: UserRole[]) => boolean;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUserState] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthStatus>(() => (tokenStorage.getToken() ? "loading" : "unauthenticated"));

  const clearSession = useCallback(() => {
    tokenStorage.clear();
    setUserState(null);
    setStatus("unauthenticated");
  }, []);

  // Restore the session on first load.
  useEffect(() => {
    if (!tokenStorage.getToken()) return;
    const controller = new AbortController();
    authApi
      .me(controller.signal)
      .then((me) => {
        setUserState(me);
        setStatus("authenticated");
      })
      .catch((error: Error) => {
        if (error.name !== "AbortError") clearSession();
      });
    return () => controller.abort();
  }, [clearSession]);

  // Any authenticated request rejected with 401 (expired/revoked token) signs the user out.
  useEffect(() => {
    setUnauthorizedHandler(clearSession);
    return () => setUnauthorizedHandler(null);
  }, [clearSession]);

  // Sign out when the token expires while the page is open.
  useEffect(() => {
    if (status !== "authenticated") return;
    const expiresAt = tokenStorage.getExpiresAt();
    if (!expiresAt) return;
    // setTimeout overflows above ~24.8 days, so cap the delay.
    const delay = Math.min(Math.max(0, expiresAt - Date.now()), 2 ** 31 - 1);
    const timer = window.setTimeout(clearSession, delay);
    return () => window.clearTimeout(timer);
  }, [status, clearSession]);

  // Keep tabs in sync: logging out in one tab logs out the others.
  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      if (event.key === tokenStorage.TOKEN_KEY && !event.newValue) clearSession();
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [clearSession]);

  const login = useCallback(async (email: string, password: string) => {
    const result = await authApi.login(email.trim(), password);
    tokenStorage.save(result.access_token, result.expires_in);
    setUserState(result.user);
    setStatus("authenticated");
    return result.user;
  }, []);

  const signup = useCallback(
    async (payload: SignupPayload) => {
      await authApi.signup(payload);
      return login(payload.email, payload.password);
    },
    [login],
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // The local session is cleared regardless; the server token may already be invalid.
    } finally {
      clearSession();
    }
  }, [clearSession]);

  const hasRole = useCallback((...roles: UserRole[]) => !!user && roles.includes(user.role), [user]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      isAuthenticated: status === "authenticated",
      login,
      signup,
      logout,
      setUser: setUserState,
      hasRole,
    }),
    [status, user, login, signup, logout, hasRole],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}

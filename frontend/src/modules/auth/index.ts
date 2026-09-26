// Public surface of the auth module for the rest of the frontend.
export { AuthProvider, useAuth } from "./AuthContext";
export type { AuthContextValue } from "./AuthContext";
export { ProtectedRoute, PublicOnlyRoute, DEFAULT_AUTHENTICATED_PATH, LOGIN_PATH } from "./routeGuards";
export { ROLE_LABELS } from "./types";
export type { User, UserRole } from "./types";

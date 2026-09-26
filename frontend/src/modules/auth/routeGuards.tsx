import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "./AuthContext";
import type { UserRole } from "./types";

/** Where users land after signing in. The Dashboard module owns the page at this path. */
export const DEFAULT_AUTHENTICATED_PATH = "/dashboard";
export const LOGIN_PATH = "/login";

function FullPageLoader() {
  return (
    <div className="page-loader" role="status" aria-live="polite">
      Loading…
    </div>
  );
}

/**
 * Wrap routes that require a signed-in user. Unauthenticated visitors go to /login and are
 * returned to the page they asked for after signing in. Pass `roles` to restrict further.
 */
export function ProtectedRoute({ roles }: { roles?: UserRole[] }) {
  const { status, user } = useAuth();
  const location = useLocation();

  if (status === "loading") return <FullPageLoader />;
  if (status === "unauthenticated") return <Navigate to={LOGIN_PATH} replace state={{ from: location }} />;
  if (roles && user && !roles.includes(user.role)) return <Navigate to={DEFAULT_AUTHENTICATED_PATH} replace />;
  return <Outlet />;
}

/** Wrap login/signup/reset pages: signed-in users are sent to the dashboard instead. */
export function PublicOnlyRoute() {
  const { status } = useAuth();
  if (status === "loading") return <FullPageLoader />;
  if (status === "authenticated") return <Navigate to={DEFAULT_AUTHENTICATED_PATH} replace />;
  return <Outlet />;
}

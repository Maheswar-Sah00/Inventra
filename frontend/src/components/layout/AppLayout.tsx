import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { LOGIN_PATH, ROLE_LABELS, useAuth } from "../../modules/auth";

/**
 * Sidebar navigation. Each module adds its own entry here (Products, Operations, Move History,
 * Settings...) when its pages exist.
 */
export const NAV_ITEMS: { to: string; label: string }[] = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/receipts", label: "Receipts" },
  { to: "/deliveries", label: "Delivery Orders" },
  { to: "/transfers", label: "Internal Transfers" },
  { to: "/adjustments", label: "Adjustments" },
  { to: "/move-history", label: "Move History" },
  { to: "/stock-availability", label: "Stock" },
  { to: "/products", label: "Products" },
  { to: "/categories", label: "Categories" },
  { to: "/units", label: "Units of Measure" },
  { to: "/reorder-rules", label: "Reordering Rules" },
  { to: "/warehouses", label: "Warehouses" },
  { to: "/locations", label: "Locations" },
];

export function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [loggingOut, setLoggingOut] = useState(false);

  async function handleLogout() {
    setLoggingOut(true);
    await logout();
    navigate(LOGIN_PATH, { replace: true });
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">StockSense</div>
        <nav className="sidebar-nav" aria-label="Main">
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.to} to={item.to} className="nav-link">
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="profile-menu" aria-label="Profile menu">
          {user && (
            <div className="profile-summary">
              <span className="profile-name">{user.name}</span>
              <span className="profile-role">{ROLE_LABELS[user.role]}</span>
            </div>
          )}
          <NavLink to="/profile" className="nav-link">
            My Profile
          </NavLink>
          <button type="button" className="nav-link nav-button" onClick={handleLogout} disabled={loggingOut}>
            {loggingOut ? "Logging out…" : "Logout"}
          </button>
        </div>
      </aside>
      <main className="app-content">
        <Outlet />
      </main>
    </div>
  );
}

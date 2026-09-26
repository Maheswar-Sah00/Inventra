import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { LOGIN_PATH, ROLE_LABELS, useAuth } from "../../modules/auth";

/**
 * Sidebar navigation, grouped as in the project brief. Modules add their pages to a section here.
 */
export const NAV_SECTIONS: { title?: string; items: { to: string; label: string }[] }[] = [
  { items: [{ to: "/dashboard", label: "Dashboard" }] },
  {
    title: "Products",
    items: [
      { to: "/products", label: "Products" },
      { to: "/stock-availability", label: "Stock Availability" },
      { to: "/categories", label: "Categories" },
      { to: "/units", label: "Units of Measure" },
      { to: "/reorder-rules", label: "Reordering Rules" },
    ],
  },
  {
    title: "Operations",
    items: [
      { to: "/receipts", label: "Receipts" },
      { to: "/deliveries", label: "Delivery Orders" },
      { to: "/transfers", label: "Internal Transfers" },
      { to: "/adjustments", label: "Inventory Adjustments" },
      { to: "/move-history", label: "Move History" },
    ],
  },
  {
    title: "Settings",
    items: [
      { to: "/warehouses", label: "Warehouses" },
      { to: "/locations", label: "Locations" },
    ],
  },
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
          {NAV_SECTIONS.map((section, index) => (
            <div key={section.title ?? index} className="nav-section">
              {section.title && <p className="nav-section-title">{section.title}</p>}
              {section.items.map((item) => (
                <NavLink key={item.to} to={item.to} className="nav-link">
                  {item.label}
                </NavLink>
              ))}
            </div>
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

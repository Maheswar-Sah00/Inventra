import { useEffect, useState, type FormEvent } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import { LOGIN_PATH, ROLE_LABELS, useAuth } from "../../modules/auth";
import { Brand } from "../ui/Brand";
import { Icon, type IconName } from "../ui/Icon";

type NavItem = { to: string; label: string; icon: IconName };

/**
 * Sidebar navigation, grouped as in the project brief. Modules add their pages to a section here.
 */
export const NAV_SECTIONS: { title?: string; items: NavItem[] }[] = [
  { items: [{ to: "/dashboard", label: "Dashboard", icon: "dashboard" }] },
  {
    title: "Products",
    items: [
      { to: "/products", label: "Products", icon: "package" },
      { to: "/stock-availability", label: "Stock Availability", icon: "chart" },
      { to: "/categories", label: "Categories", icon: "tag" },
      { to: "/units", label: "Units of Measure", icon: "ruler" },
      { to: "/reorder-rules", label: "Reordering Rules", icon: "refresh" },
    ],
  },
  {
    title: "Operations",
    items: [
      { to: "/receipts", label: "Receipts", icon: "inbox" },
      { to: "/deliveries", label: "Delivery Orders", icon: "truck" },
      { to: "/transfers", label: "Internal Transfers", icon: "transfer" },
      { to: "/adjustments", label: "Inventory Adjustments", icon: "clipboard" },
      { to: "/move-history", label: "Move History", icon: "history" },
    ],
  },
  {
    title: "Settings",
    items: [
      { to: "/warehouses", label: "Warehouses", icon: "warehouse" },
      { to: "/locations", label: "Locations", icon: "pin" },
    ],
  },
];

const COLLAPSED_KEY = "stocksense.nav.collapsed";

/** Collapsed sidebar sections, remembered per browser. Storage can be unavailable (private mode), so reads and writes are guarded. */
function useCollapsedSections() {
  const [collapsed, setCollapsed] = useState<string[]>(() => {
    try {
      const stored: unknown = JSON.parse(localStorage.getItem(COLLAPSED_KEY) ?? "[]");
      // Ignore anything that is not a list of section titles (old or hand-edited values).
      return Array.isArray(stored) ? stored.filter((t): t is string => typeof t === "string") : [];
    } catch {
      return [];
    }
  });
  function toggle(title: string) {
    setCollapsed((current) => {
      const next = current.includes(title) ? current.filter((t) => t !== title) : [...current, title];
      try {
        localStorage.setItem(COLLAPSED_KEY, JSON.stringify(next));
      } catch {
        // Not persisted; the section still toggles for this visit.
      }
      return next;
    });
  }
  return { collapsed, toggle };
}

function initials(name: string) {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

function greeting(date: Date) {
  const hour = date.getHours();
  return hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
}

function TopBar() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const now = new Date();

  function handleSearch(event: FormEvent) {
    event.preventDefault();
    const q = query.trim();
    navigate(q ? `/products?q=${encodeURIComponent(q)}` : "/products");
    setQuery("");
  }

  return (
    <header className="topbar">
      <div className="topbar-greeting">
        <span className="topbar-date">{now.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })}</span>
        <span className="topbar-hello">
          {greeting(now)}
          {user ? `, ${user.name.split(" ")[0]}` : ""}
        </span>
      </div>
      <form role="search" className="topbar-search" onSubmit={handleSearch}>
        <Icon name="search" />
        <input
          type="search"
          aria-label="Search products"
          placeholder="Search products or SKU…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </form>
      <Link to="/stock-availability?status=LOW_STOCK,OUT_OF_STOCK" className="icon-button" aria-label="Stock alerts" title="Stock alerts">
        <Icon name="bell" />
      </Link>
      {user && (
        <Link to="/profile" className="avatar-chip">
          <span className="avatar" aria-hidden="true">
            {initials(user.name)}
          </span>
          <span className="avatar-meta">
            <span className="avatar-name">{user.name}</span>
            <span className="avatar-role">{ROLE_LABELS[user.role]}</span>
          </span>
        </Link>
      )}
    </header>
  );
}

export function AppLayout() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [loggingOut, setLoggingOut] = useState(false);
  // On small screens the menu is collapsed behind a toggle; it closes after navigating.
  const [menuOpen, setMenuOpen] = useState(false);
  const { pathname } = useLocation();
  useEffect(() => setMenuOpen(false), [pathname]);
  const sections = useCollapsedSections();

  async function handleLogout() {
    setLoggingOut(true);
    await logout();
    navigate(LOGIN_PATH, { replace: true });
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar${menuOpen ? " open" : ""}`}>
        <div className="sidebar-header">
          <Link to="/dashboard" className="brand-link">
            <Brand />
          </Link>
          <button
            type="button"
            className="menu-toggle"
            aria-expanded={menuOpen}
            aria-controls="main-navigation"
            onClick={() => setMenuOpen((open) => !open)}
          >
            <Icon name={menuOpen ? "close" : "menu"} />
            {menuOpen ? "Close" : "Menu"}
          </button>
        </div>
        <nav id="main-navigation" className="sidebar-nav" aria-label="Main">
          {NAV_SECTIONS.map((section, index) => {
            const collapsed = section.title ? sections.collapsed.includes(section.title) : false;
            return (
              <div key={section.title ?? index} className="nav-section">
                {section.title && (
                  <button
                    type="button"
                    className="nav-section-title"
                    aria-expanded={!collapsed}
                    onClick={() => sections.toggle(section.title!)}
                  >
                    <span>{section.title}</span>
                    <Icon name="chevronDown" size={14} />
                  </button>
                )}
                {!collapsed &&
                  section.items.map((item) => (
                    <NavLink key={item.to} to={item.to} className="nav-link">
                      <Icon name={item.icon} />
                      <span>{item.label}</span>
                    </NavLink>
                  ))}
              </div>
            );
          })}
        </nav>
        <div className="sidebar-promo surface-dark">
          <p className="sidebar-promo-title">Goods arriving?</p>
          <p className="sidebar-promo-text">Record a receipt and stock updates the moment it is validated.</p>
          <Link to="/receipts/new" className="btn btn-glass">
            <Icon name="plus" size={16} />
            New receipt
          </Link>
        </div>
        <div className="profile-menu" aria-label="Profile menu">
          <NavLink to="/profile" className="nav-link">
            <Icon name="user" />
            <span>My Profile</span>
          </NavLink>
          <button type="button" className="nav-link nav-button" onClick={handleLogout} disabled={loggingOut}>
            <Icon name="logout" />
            <span>{loggingOut ? "Logging out…" : "Logout"}</span>
          </button>
        </div>
      </aside>
      <div className="app-main">
        <TopBar />
        <main className="app-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

import { useAuth } from "../modules/auth";

/**
 * PLACEHOLDER — the Dashboard module replaces this page (route: /dashboard).
 * It exists only so the post-login redirect has a destination.
 */
export function DashboardPlaceholderPage() {
  const { user } = useAuth();
  return (
    <section className="page">
      <h1>Inventory Dashboard</h1>
      <p className="muted">Welcome{user ? `, ${user.name}` : ""}. The inventory dashboard will appear here.</p>
    </section>
  );
}

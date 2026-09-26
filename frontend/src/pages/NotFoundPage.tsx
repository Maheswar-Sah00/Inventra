import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <main className="auth-page">
      <div className="auth-card">
        <h1>Page not found</h1>
        <p className="muted">The page you are looking for doesn't exist.</p>
        <Link to="/">Go to StockSense</Link>
      </div>
    </main>
  );
}

import type { ReactNode } from "react";

import { Brand } from "../ui/Brand";
import { Icon, type IconName } from "../ui/Icon";

const HIGHLIGHTS: { icon: IconName; title: string; text: string }[] = [
  { icon: "warehouse", title: "Every warehouse, one view", text: "Live stock per product, rack and location." },
  { icon: "transfer", title: "Receive, move, deliver", text: "Receipts, transfers and deliveries in one flow." },
  { icon: "history", title: "A ledger you can trust", text: "Every stock change, who made it and when." },
];

/** Two-panel page used by the login, signup and password reset screens. The brand panel hides on small screens. */
export function AuthLayout({ title, subtitle, children, footer }: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <main className="auth-page">
      <section className="auth-hero surface-dark" aria-hidden="true">
        <Brand inverse />
        <div className="auth-hero-copy">
          <p className="auth-hero-kicker">Inventory management</p>
          <p className="auth-hero-title">Stock you can see, moves you can trust.</p>
        </div>
        <ul className="auth-hero-list">
          {HIGHLIGHTS.map((item) => (
            <li key={item.title}>
              <span className="auth-hero-icon">
                <Icon name={item.icon} />
              </span>
              <span>
                <strong>{item.title}</strong>
                <span>{item.text}</span>
              </span>
            </li>
          ))}
        </ul>
      </section>
      <div className="auth-panel">
        <div className="auth-card">
          <div className="auth-card-brand">
            <Brand />
          </div>
          <h1>{title}</h1>
          {subtitle && <p className="muted">{subtitle}</p>}
          {children}
          {footer && <div className="auth-footer">{footer}</div>}
        </div>
      </div>
    </main>
  );
}

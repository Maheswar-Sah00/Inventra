import type { ReactNode } from "react";

export function Alert({ variant, children }: { variant: "error" | "success" | "info"; children: ReactNode }) {
  return (
    <div className={`alert alert-${variant}`} role={variant === "error" ? "alert" : "status"}>
      {children}
    </div>
  );
}

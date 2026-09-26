import type { ButtonHTMLAttributes } from "react";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "link";
  loading?: boolean;
  loadingText?: string;
};

export function Button({ variant = "primary", loading = false, loadingText, children, disabled, ...rest }: ButtonProps) {
  return (
    <button className={`btn btn-${variant}`} disabled={disabled || loading} aria-busy={loading} {...rest}>
      {loading ? (loadingText ?? "Please wait…") : children}
    </button>
  );
}

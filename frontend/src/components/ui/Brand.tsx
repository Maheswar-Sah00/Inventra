/** StockSense wordmark: a stacked-boxes mark next to the name. */
export function Brand({ inverse = false }: { inverse?: boolean }) {
  return (
    <span className={`brand${inverse ? " brand-inverse" : ""}`}>
      <span className="brand-mark" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round">
          <path d="M12 3 4 7l8 4 8-4-8-4Z" />
          <path d="m4 12 8 4 8-4" />
          <path d="m4 17 8 4 8-4" />
        </svg>
      </span>
      <span className="brand-name">StockSense</span>
    </span>
  );
}

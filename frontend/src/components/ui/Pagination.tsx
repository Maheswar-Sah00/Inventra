export function Pagination({
  total,
  limit,
  offset,
  onChange,
}: {
  total: number;
  limit: number;
  offset: number;
  onChange: (offset: number) => void;
}) {
  if (total <= limit) return total ? <p className="pagination muted small">{total} total</p> : null;
  const first = offset + 1;
  const last = Math.min(offset + limit, total);
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.ceil(total / limit);
  return (
    <nav className="pagination" aria-label="Pagination">
      <span className="muted small" aria-live="polite">
        Page {page} of {pages} · {first}–{last} of {total}
      </span>
      <button type="button" className="btn btn-secondary" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>
        Previous
      </button>
      <button type="button" className="btn btn-secondary" disabled={last >= total} onClick={() => onChange(offset + limit)}>
        Next
      </button>
    </nav>
  );
}

export function StatusBadge({ active }: { active: boolean }) {
  return <span className={`badge ${active ? "badge-success" : "badge-muted"}`}>{active ? "Active" : "Inactive"}</span>;
}

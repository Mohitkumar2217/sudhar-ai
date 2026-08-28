import { Invoice, formatCents } from "@/lib/api";
import StatusPill from "./StatusPill";

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "PENDING", label: "Pending" },
  { value: "SCHEDULED_RETRY", label: "Retry scheduled" },
  { value: "DUNNING_ACTIVE", label: "Dunning active" },
  { value: "FRAUD_REVIEW", label: "Fraud review" },
  { value: "RECOVERED", label: "Recovered" },
  { value: "FAILED_EXHAUSTED", label: "Exhausted" },
];

export default function InvoiceTable({
  invoices,
  statusFilter,
  onStatusFilterChange,
  search,
  onSearchChange,
}: {
  invoices: Invoice[];
  statusFilter: string;
  onStatusFilterChange: (v: string) => void;
  search: string;
  onSearchChange: (v: string) => void;
}) {
  const filtered = invoices.filter((inv) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      (inv.customer_name || "").toLowerCase().includes(q) ||
      inv.customer_email.toLowerCase().includes(q) ||
      inv.invoice_id.toLowerCase().includes(q)
    );
  });

  return (
    <div>
      <div className="flex flex-col sm:flex-row gap-2 mb-3">
        <input
          type="text"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search customer or invoice…"
          className="flex-1 bg-bg border border-panelBorder rounded-pill px-4 py-2 text-sm font-body text-ink placeholder:text-muted focus:border-gold outline-none"
        />
        <select
          value={statusFilter}
          onChange={(e) => onStatusFilterChange(e.target.value)}
          className="bg-bg border border-panelBorder rounded-pill px-4 py-2 text-sm font-body text-ink focus:border-gold outline-none"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>
      <InvoiceTableBody invoices={filtered} />
    </div>
  );
}

function InvoiceTableBody({ invoices }: { invoices: Invoice[] }) {
  if (invoices.length === 0) {
    return (
      <div className="text-sm text-muted py-10 text-center">
        No matching invoices. Run <code className="font-mono text-gold">python -m app.seed</code> in
        the backend to generate demo data.
      </div>
    );
  }

  return (
    <div className="overflow-y-auto max-h-[420px]">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-panel">
          <tr className="text-left text-muted font-display text-[11px] uppercase tracking-[0.1em] border-b border-panelBorder">
            <th className="py-2 pr-3 font-medium">Customer</th>
            <th className="py-2 pr-3 font-medium">Amount</th>
            <th className="py-2 pr-3 font-medium">Reason</th>
            <th className="py-2 pr-3 font-medium">Status</th>
            <th className="py-2 pr-3 font-medium text-right">Attempts</th>
          </tr>
        </thead>
        <tbody>
          {invoices.map((inv) => (
            <tr key={inv.id} className="border-b border-panelBorder/60 hover:bg-black/[0.02]">
              <td className="py-2.5 pr-3">
                <div className="text-ink">{inv.customer_name || inv.customer_email}</div>
                <div className="text-xs text-muted font-mono">{inv.invoice_id}</div>
              </td>
              <td className="py-2.5 pr-3 font-mono text-ink">
                {formatCents(inv.amount_due_cents)}
              </td>
              <td className="py-2.5 pr-3 text-muted font-mono text-xs">
                {inv.raw_decline_code.replaceAll("_", " ")}
              </td>
              <td className="py-2.5 pr-3">
                <StatusPill status={inv.status} />
              </td>
              <td className="py-2.5 pr-3 text-right font-mono text-muted">
                {inv.attempt_count}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}


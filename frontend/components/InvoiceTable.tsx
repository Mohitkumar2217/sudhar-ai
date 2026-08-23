import { Invoice, formatCents } from "@/lib/api";
import StatusPill from "./StatusPill";

export default function InvoiceTable({ invoices }: { invoices: Invoice[] }) {
  if (invoices.length === 0) {
    return (
      <div className="text-sm text-muted py-10 text-center">
        No failed invoices yet. Run <code className="font-mono text-gold">python -m app.seed</code> in
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

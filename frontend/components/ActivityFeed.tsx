import { ActivityAction, formatCents } from "@/lib/api";

const ACTION_LABELS: Record<string, string> = {
  DUNNING_EMAIL: "Dunning email sent",
  HEADLESS_RETRY: "Silent retry attempted",
  CARD_UPDATED: "Card updated via portal",
};

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function ActivityFeed({ actions }: { actions: ActivityAction[] }) {
  if (actions.length === 0) {
    return <p className="text-sm text-muted font-body py-4">No activity yet.</p>;
  }

  return (
    <ul className="divide-y divide-panelBorder/60">
      {actions.map((a) => (
        <li key={a.id} className="py-2.5 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm text-ink font-body truncate">
              {ACTION_LABELS[a.action_type] || a.action_type}
              {a.customer_name && (
                <span className="text-muted"> — {a.customer_name}</span>
              )}
            </p>
            <p className="text-xs text-muted font-mono">
              {a.invoice_ref}
              {a.amount_due_cents != null && ` · ${formatCents(a.amount_due_cents)}`}
            </p>
          </div>
          <div className="flex flex-col items-end shrink-0">
            <span
              className={`w-2 h-2 rounded-full ${
                a.is_successful === false ? "bg-rust" : "bg-gold"
              }`}
              aria-hidden="true"
            />
            <span className="text-[11px] text-muted font-mono mt-1">
              {timeAgo(a.created_at)}
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
}

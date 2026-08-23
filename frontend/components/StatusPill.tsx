const STATUS_STYLES: Record<string, string> = {
  PENDING: "bg-panelBorder text-muted",
  SCHEDULED_RETRY: "bg-goldDim text-gold",
  DUNNING_ACTIVE: "bg-rustDim text-rust",
  RECOVERED: "bg-goldDim text-gold",
  FAILED_EXHAUSTED: "bg-rustDim text-rust",
};

const STATUS_LABELS: Record<string, string> = {
  PENDING: "Pending",
  SCHEDULED_RETRY: "Retry scheduled",
  DUNNING_ACTIVE: "Dunning active",
  RECOVERED: "Recovered",
  FAILED_EXHAUSTED: "Exhausted",
};

export default function StatusPill({ status }: { status: string }) {
  const style = STATUS_STYLES[status] || "bg-panelBorder text-muted";
  const label = STATUS_LABELS[status] || status;
  return (
    <span
      className={`inline-block font-mono text-[11px] px-2 py-1 rounded ${style} whitespace-nowrap`}
    >
      {label}
    </span>
  );
}

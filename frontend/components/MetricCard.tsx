import { ReactNode } from "react";

export default function MetricCard({
  label,
  value,
  tone = "neutral",
  footnote,
  children,
}: {
  label: string;
  value: string;
  tone?: "neutral" | "gold" | "rust";
  footnote?: string;
  children?: ReactNode;
}) {
  const valueColor =
    tone === "gold" ? "text-gold" : tone === "rust" ? "text-rust" : "text-ink";

  return (
    <div className="bg-panel border border-panelBorder rounded-lg p-5 flex flex-col gap-2">
      <span className="font-display text-[11px] tracking-[0.14em] uppercase text-muted">
        {label}
      </span>
      <span className={`font-mono text-3xl font-medium ${valueColor}`}>{value}</span>
      {footnote && <span className="text-xs text-muted">{footnote}</span>}
      {children}
    </div>
  );
}

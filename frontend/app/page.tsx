"use client";

import { useCallback, useEffect, useState } from "react";
import { api, DashboardSummary, Invoice, formatCents } from "@/lib/api";
import MetricCard from "@/components/MetricCard";
import PulseLine from "@/components/PulseLine";
import InvoiceTable from "@/components/InvoiceTable";
import CopilotPanel from "@/components/CopilotPanel";

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [cycling, setCycling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [s, i] = await Promise.all([api.getSummary(), api.getInvoices()]);
      setSummary(s);
      setInvoices(i);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? `${err.message} — is the backend running at localhost:8000?`
          : "Couldn't reach the backend."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleRunCycle() {
    setCycling(true);
    try {
      await api.runRecoveryCycle();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Recovery cycle failed.");
    } finally {
      setCycling(false);
    }
  }

  const recoveryRatePct =
    summary?.recovery_rate != null ? `${(summary.recovery_rate * 100).toFixed(1)}%` : "—";

  return (
    <main className="min-h-screen bg-bg px-6 py-6 md:px-10 md:py-8">
      {/* Top bar */}
      <header className="flex items-center justify-between mb-8 pb-4 border-b border-panelBorder">
        <div className="flex items-baseline gap-3">
          <span className="font-display text-gold text-xl">सुधार</span>
          <div className="flex flex-col leading-tight">
            <span className="font-display font-semibold text-ink tracking-tight">
              Sudhar AI
            </span>
            <span className="text-xs text-muted">Operations console</span>
          </div>
        </div>
        <button
          onClick={handleRunCycle}
          disabled={cycling}
          className="font-display text-sm font-medium border border-gold text-gold rounded-pill px-5 py-2.5 hover:bg-gold hover:text-panel transition disabled:opacity-50"
        >
          {cycling ? "Running cycle…" : "Run recovery cycle"}
        </button>
      </header>

      {error && (
        <div className="bg-rustDim border border-rust/40 text-rust text-sm rounded-md px-4 py-3 mb-6 font-mono">
          {error}
        </div>
      )}

      {/* Metric cards */}
      <section className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <MetricCard
          label="Revenue at risk"
          value={loading ? "—" : formatCents(summary?.revenue_at_risk_cents ?? 0)}
          tone="rust"
          footnote="Open, retrying, or in dunning"
        />
        <MetricCard
          label="Revenue recovered"
          value={loading ? "—" : formatCents(summary?.revenue_recovered_cents ?? 0)}
          tone="gold"
        >
          <PulseLine />
        </MetricCard>
        <MetricCard
          label="Recovery rate"
          value={loading ? "—" : recoveryRatePct}
          footnote="Recovered / (recovered + exhausted)"
        />
      </section>

      {/* Top failure reasons strip */}
      {summary && summary.top_failure_reasons.length > 0 && (
        <section className="mb-6 flex flex-wrap gap-2">
          {summary.top_failure_reasons.map((r) => (
            <span
              key={r.reason}
              className="font-mono text-xs border border-panelBorder rounded px-2.5 py-1.5 text-muted"
            >
              <span className="text-ink">{r.reason.replaceAll("_", " ")}</span>
              <span className="text-gold ml-2">{r.count}</span>
            </span>
          ))}
        </section>
      )}

      {/* Main grid: invoices + copilot */}
      <section className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-3 bg-panel border border-panelBorder rounded-lg p-5">
          <h2 className="font-display text-sm font-semibold text-ink mb-3">
            Failed invoices
          </h2>
          <InvoiceTable invoices={invoices} />
        </div>

        <div className="lg:col-span-2 bg-panel border border-panelBorder rounded-lg p-5 flex flex-col min-h-[420px]">
          <h2 className="font-display text-sm font-semibold text-ink mb-3">
            CFO Copilot
          </h2>
          <CopilotPanel />
        </div>
      </section>
    </main>
  );
}

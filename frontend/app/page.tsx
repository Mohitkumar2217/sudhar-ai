"use client";

import { useCallback, useEffect, useState } from "react";
import { api, DashboardSummary, Invoice, ModelStatus, ActivityAction, formatCents } from "@/lib/api";
import MetricCard from "@/components/MetricCard";
import PulseLine from "@/components/PulseLine";
import InvoiceTable from "@/components/InvoiceTable";
import CopilotWidget from "@/components/CopilotWidget";
import ModelStatusPanel from "@/components/ModelStatusPanel";
import FailureReasonsChart from "@/components/FailureReasonsChart";
import ActivityFeed from "@/components/ActivityFeed";
import RecoveryPipeline from "@/components/RecoveryPipeline";

const LIVE_REFRESH_MS = 10000;

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const [activity, setActivity] = useState<ActivityAction[]>([]);
  const [loading, setLoading] = useState(true);
  const [cycling, setCycling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [liveMode, setLiveMode] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");

  const load = useCallback(async (opts?: { silent?: boolean }) => {
    if (!opts?.silent) setLoading(true);
    try {
      const [s, i, m, a] = await Promise.all([
        api.getSummary(),
        api.getInvoices(statusFilter || undefined),
        api.getModelStatus(),
        api.getActivity(15),
      ]);
      setSummary(s);
      setInvoices(i);
      setModelStatus(m);
      setActivity(a);
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
  }, [statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  // Live mode: poll silently in the background so numbers update without a
  // full-page loading flash — this is what makes "Run recovery cycle" feel
  // like a live operations console rather than a static report.
  useEffect(() => {
    if (!liveMode) return;
    const interval = setInterval(() => load({ silent: true }), LIVE_REFRESH_MS);
    return () => clearInterval(interval);
  }, [liveMode, load]);

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
      <header className="flex flex-wrap items-center justify-between gap-3 mb-8 pb-4 border-b border-panelBorder">
        <div className="flex items-baseline gap-3">
          <span className="font-display text-gold text-xl">सुधार</span>
          <div className="flex flex-col leading-tight">
            <span className="font-display font-semibold text-ink tracking-tight">
              Sudhar AI
            </span>
            <span className="text-xs text-muted">Operations console</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setLiveMode((v) => !v)}
            aria-pressed={liveMode}
            className="flex items-center gap-2 font-display text-sm font-medium text-muted hover:text-ink transition"
          >
            <span
              className={`w-2 h-2 rounded-full ${liveMode ? "bg-gold animate-pulse" : "bg-panelBorder"}`}
              aria-hidden="true"
            />
            {liveMode ? "Live" : "Live off"}
          </button>
          <button
            onClick={handleRunCycle}
            disabled={cycling}
            className="font-display text-sm font-medium border border-gold text-gold rounded-pill px-5 py-2.5 hover:bg-gold hover:text-panel transition disabled:opacity-50"
          >
            {cycling ? "Running cycle…" : "Run recovery cycle"}
          </button>
        </div>
      </header>

      {error && (
        <div className="bg-rustDim border border-rust/40 text-rust text-sm rounded-md px-4 py-3 mb-6 font-mono">
          {error}
        </div>
      )}

      {/* Metric cards */}
      <section className="section-3d grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
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

      {/* Live recovery pipeline — the real-time view of invoices moving through stages */}
      <section className="mb-6">
        <RecoveryPipeline counts={summary?.pipeline_counts ?? {}} live={liveMode} />
      </section>

      {/* Main grid: invoices + side column */}
      <section className="section-3d grid grid-cols-1 lg:grid-cols-5 gap-4 mb-4">
        <div className="section-3d-item lg:col-span-3 bg-panel border border-panelBorder rounded-lg p-5">
          <h2 className="font-display text-sm font-semibold text-ink mb-3">
            Failed invoices
          </h2>
          <InvoiceTable
            invoices={invoices}
            statusFilter={statusFilter}
            onStatusFilterChange={setStatusFilter}
            search={search}
            onSearchChange={setSearch}
          />
        </div>

        <div className="lg:col-span-2 flex flex-col gap-4">
          <ModelStatusPanel status={modelStatus} />

          {summary && summary.top_failure_reasons.length > 0 && (
            <div className="section-3d-item bg-panel border border-panelBorder rounded-lg p-5">
              <h2 className="font-display text-sm font-semibold text-ink mb-2">
                Top failure reasons
              </h2>
              <FailureReasonsChart reasons={summary.top_failure_reasons} />
            </div>
          )}
        </div>
      </section>

      {/* Activity feed */}
      <section className="section-3d">
        <div className="section-3d-item bg-panel border border-panelBorder rounded-lg p-5 max-h-[420px] overflow-y-auto">
          <h2 className="font-display text-sm font-semibold text-ink mb-1">
            Recent activity
          </h2>
          <ActivityFeed actions={activity} />
        </div>
      </section>

      {/* CFO Copilot: floating icon, opens on demand instead of an always-visible panel */}
      <CopilotWidget />
    </main>
  );
}


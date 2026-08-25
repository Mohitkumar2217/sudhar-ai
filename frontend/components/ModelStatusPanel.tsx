import { ModelStatus } from "@/lib/api";

export default function ModelStatusPanel({ status }: { status: ModelStatus | null }) {
  if (!status) return null;

  if (!status.trained) {
    return (
      <div className="bg-panel border border-panelBorder rounded-lg p-5">
        <h2 className="font-display text-sm font-semibold text-ink mb-2">
          Retry-timing model
        </h2>
        <p className="text-sm text-muted font-body">
          Not trained yet. Run{" "}
          <code className="font-mono text-gold text-xs">
            python -m scripts.train_retry_model
          </code>{" "}
          in the backend.
        </p>
      </div>
    );
  }

  const trainedDate = status.trained_at
    ? new Date(status.trained_at).toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
      })
    : "unknown date";

  return (
    <div className="bg-panel border border-panelBorder rounded-lg p-5">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-display text-sm font-semibold text-ink">
          Retry-timing model
        </h2>
        <span
          className={`font-mono text-[11px] px-2 py-1 rounded ${
            status.active ? "bg-goldDim text-gold" : "bg-panelBorder text-muted"
          }`}
        >
          {status.active ? "Active" : "Inactive"}
        </span>
      </div>

      {status.is_synthetic && (
        <div className="bg-rustDim border border-rust/30 rounded-md px-3 py-2 mb-3">
          <p className="text-xs text-rust font-body leading-relaxed">
            Trained on <strong>synthetic</strong> data — not real recovery
            outcomes. Scheduling still uses the heuristic unless this is
            explicitly enabled. See README Step 12.
          </p>
        </div>
      )}

      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <dt className="text-muted font-body">Trained</dt>
        <dd className="text-ink font-mono text-right">{trainedDate}</dd>

        <dt className="text-muted font-body">Samples</dt>
        <dd className="text-ink font-mono text-right">
          {status.n_samples?.toLocaleString() ?? "—"}
        </dd>

        <dt className="text-muted font-body">Test AUC</dt>
        <dd className="text-ink font-mono text-right">{status.test_auc ?? "—"}</dd>

        <dt className="text-muted font-body">Brier score</dt>
        <dd className="text-ink font-mono text-right">
          {status.test_brier_score ?? "—"}
        </dd>
      </dl>
    </div>
  );
}

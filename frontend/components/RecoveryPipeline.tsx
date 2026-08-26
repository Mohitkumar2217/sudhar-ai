const STAGES: { key: string; label: string }[] = [
  { key: "PENDING", label: "New" },
  { key: "SCHEDULED_RETRY", label: "Retrying" },
  { key: "DUNNING_ACTIVE", label: "Dunning" },
  { key: "RECOVERED", label: "Recovered" },
  { key: "FAILED_EXHAUSTED", label: "Exhausted" },
];

// Reuses the same two-accent system as the rest of the app: gold for the
// positive terminal state, rust for the negative one, neutral for in-flight.
const STAGE_TONE: Record<string, string> = {
  PENDING: "text-ink",
  SCHEDULED_RETRY: "text-ink",
  DUNNING_ACTIVE: "text-rust",
  RECOVERED: "text-gold",
  FAILED_EXHAUSTED: "text-rust",
};

export default function RecoveryPipeline({
  counts,
  live,
}: {
  counts: Record<string, number>;
  live: boolean;
}) {
  return (
    <div className="bg-panel border border-panelBorder rounded-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-display text-sm font-semibold text-ink">
          Recovery pipeline
        </h2>
        {live && (
          <span className="flex items-center gap-1.5 text-[11px] font-mono text-muted">
            <span className="w-1.5 h-1.5 rounded-full bg-gold animate-pulse" aria-hidden="true" />
            live
          </span>
        )}
      </div>

      <div className="flex items-stretch">
        {STAGES.map((stage, i) => (
          <div key={stage.key} className="flex items-stretch flex-1">
            <div className="flex flex-col items-center text-center flex-1 px-1">
              <span className={`font-mono text-2xl md:text-3xl font-medium ${STAGE_TONE[stage.key]}`}>
                {counts[stage.key] ?? 0}
              </span>
              <span className="font-display text-[11px] uppercase tracking-[0.1em] text-muted mt-1">
                {stage.label}
              </span>
            </div>
            {i < STAGES.length - 1 && (
              <div className="flex items-center px-1 md:px-2 text-panelBorder" aria-hidden="true">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M6 3l5 5-5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

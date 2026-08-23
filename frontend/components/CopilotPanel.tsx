"use client";

import { FormEvent, useState } from "react";
import { api, CopilotResponse } from "@/lib/api";

const SUGGESTED_QUESTIONS = [
  "How much revenue is currently at risk?",
  "What's our biggest failure reason?",
  "How many invoices are in dunning?",
];

export default function CopilotPanel() {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<CopilotResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function ask(q: string) {
    if (!q.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.askCopilot(q);
      setHistory((prev) => [result, ...prev]);
      setQuestion("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "The copilot couldn't answer that.");
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    ask(question);
  }

  return (
    <div className="flex flex-col h-full">
      <form onSubmit={handleSubmit} className="flex gap-2 mb-3">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about revenue at risk, top failure reasons..."
          className="flex-1 bg-bg border border-panelBorder rounded-pill px-4 py-2.5 text-sm font-body text-ink placeholder:text-muted focus:border-gold outline-none"
        />
        <button
          type="submit"
          disabled={loading}
          className="bg-gold text-panel font-display text-sm font-semibold px-5 py-2.5 rounded-pill hover:brightness-110 disabled:opacity-50 transition"
        >
          {loading ? "Thinking…" : "Ask"}
        </button>
      </form>

      {history.length === 0 && !error && (
        <div className="flex flex-wrap gap-2 mb-2">
          {SUGGESTED_QUESTIONS.map((q) => (
            <button
              key={q}
              onClick={() => ask(q)}
              className="text-xs font-mono text-muted border border-panelBorder rounded px-2 py-1 hover:text-gold hover:border-gold transition"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {error && (
        <p className="text-sm text-rust mb-2">{error}</p>
      )}

      <div className="flex-1 overflow-y-auto space-y-4 pr-1">
        {history.map((entry, idx) => (
          <div key={idx} className="border-l-2 border-gold/40 pl-3">
            <p className="text-xs font-mono text-muted mb-1">{entry.question}</p>
            <p className="text-sm text-ink leading-relaxed mb-2">{entry.answer}</p>
            <details className="text-xs text-muted">
              <summary className="cursor-pointer hover:text-gold font-mono">
                View query
              </summary>
              <pre className="mt-1 whitespace-pre-wrap font-mono text-[11px] bg-bg border border-panelBorder rounded p-2 text-muted">
                {entry.sql}
              </pre>
            </details>
          </div>
        ))}
      </div>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import CopilotPanel from "./CopilotPanel";

export default function CopilotWidget() {
  const [open, setOpen] = useState(false);

  // Close on Escape, so the widget behaves like a real overlay.
  useEffect(() => {
    if (!open) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [open]);

  return (
    <>
      {open && (
        <div
          className="fixed bottom-24 right-6 z-50 w-[min(380px,calc(100vw-3rem))] max-h-[70vh] bg-panel border border-panelBorder rounded-lg shadow-xl flex flex-col p-4"
          role="dialog"
          aria-label="CFO Copilot"
        >
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-display text-sm font-semibold text-ink">
              CFO Copilot
            </h2>
            <button
              onClick={() => setOpen(false)}
              aria-label="Close copilot"
              className="text-muted hover:text-ink transition"
            >
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                <path d="M4 4l10 10M14 4L4 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            </button>
          </div>
          <div className="flex-1 overflow-y-auto min-h-0">
            <CopilotPanel />
          </div>
        </div>
      )}

      <button
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? "Close CFO Copilot" : "Open CFO Copilot"}
        aria-expanded={open}
        className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-pill bg-gold text-panel shadow-lg flex items-center justify-center hover:brightness-110 transition"
      >
        {open ? (
          <svg width="20" height="20" viewBox="0 0 18 18" fill="none">
            <path d="M4 4l10 10M14 4L4 14" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
          </svg>
        ) : (
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <path
              d="M4 4h16v11a1 1 0 01-1 1H8l-4 4V5a1 1 0 011-1z"
              stroke="currentColor"
              strokeWidth="1.75"
              strokeLinejoin="round"
            />
            <circle cx="8.5" cy="9.5" r="1" fill="currentColor" />
            <circle cx="12" cy="9.5" r="1" fill="currentColor" />
            <circle cx="15.5" cy="9.5" r="1" fill="currentColor" />
          </svg>
        )}
      </button>
    </>
  );
}

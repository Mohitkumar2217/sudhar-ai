"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, PortalInvoice, formatCents } from "@/lib/api";

type ViewState = "loading" | "error" | "already_recovered" | "ready" | "success";

export default function UpdatePortalClient() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";

  const [view, setView] = useState<ViewState>("loading");
  const [invoice, setInvoice] = useState<PortalInvoice | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!token) {
      setErrorMessage("This link is missing its token — please use the link from your email.");
      setView("error");
      return;
    }
    api
      .getPortalInvoice(token)
      .then((data) => {
        setInvoice(data);
        setView(data.already_recovered ? "already_recovered" : "ready");
      })
      .catch((err) => {
        setErrorMessage(
          err instanceof Error ? err.message : "This link couldn't be verified."
        );
        setView("error");
      });
  }, [token]);

  async function handleConfirm() {
    if (!confirmed || submitting) return;
    setSubmitting(true);
    try {
      await api.updateCard(token);
      setView("success");
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Something went wrong.");
      setView("error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-bg flex flex-col">
      <header className="px-6 py-6 md:px-12">
        <span className="font-body text-sm text-muted">
          {invoice?.tenant_name || "Sudhar AI"}
        </span>
      </header>

      <div className="flex-1 flex items-start md:items-center justify-center px-6">
        <div className="w-full max-w-xl">
          {view === "loading" && (
            <p className="text-muted font-body">Loading your invoice…</p>
          )}

          {view === "error" && (
            <div>
              <h1 className="font-display font-extrabold text-3xl md:text-4xl text-gold mb-4">
                Hmm, that didn&apos;t work
              </h1>
              <p className="text-ink font-body">{errorMessage}</p>
            </div>
          )}

          {view === "already_recovered" && (
            <div>
              <h1 className="font-display font-extrabold text-3xl md:text-4xl text-gold mb-4">
                You&apos;re all set
              </h1>
              <p className="text-ink font-body">
                This subscription has already been taken care of — no further action needed.
              </p>
            </div>
          )}

          {view === "success" && (
            <div>
              <h1 className="font-display font-extrabold text-3xl md:text-4xl text-gold mb-4">
                All done
              </h1>
              <p className="text-ink font-body">
                Your payment method has been updated and your subscription is active again.
                Thanks for taking care of that.
              </p>
            </div>
          )}

          {view === "ready" && invoice && (
            <div>
              <h1 className="font-display font-extrabold text-3xl md:text-4xl text-gold mb-6 leading-tight">
                Let&apos;s get this sorted
              </h1>

              <p className="text-muted font-body mb-1">
                Hi {invoice.customer_name}, your last payment didn&apos;t go through.
              </p>
              <p className="text-ink font-body mb-6">
                {formatCents(invoice.amount_due_cents ?? 0)} for {invoice.tenant_name}
              </p>

              <label className="flex items-start gap-3 mb-8 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(e) => setConfirmed(e.target.checked)}
                  className="mt-0.5 w-5 h-5 rounded border-panelBorder text-gold focus:ring-gold accent-gold"
                />
                <span className="text-sm font-body text-ink">
                  I authorize a new charge attempt on my payment method on file.
                  <span className="text-gold"> *</span>
                </span>
              </label>

              <p className="text-xs text-muted font-body mb-8 max-w-md">
                This demo confirms the update without collecting card details. A
                real deployment embeds a gateway-hosted card form here (e.g.
                Stripe&apos;s Payment Element) — raw card data never touches this
                backend.
              </p>

              <button
                onClick={handleConfirm}
                disabled={!confirmed || submitting}
                aria-label="Confirm update"
                className="bg-gold text-panel rounded-pill w-14 h-14 flex items-center justify-center hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed transition"
              >
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                  <path
                    d="M7 4l6 6-6 6"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}

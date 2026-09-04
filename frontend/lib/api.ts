const API_URL = process.env.NEXT_API_URL || "http://localhost:8000";

export type Invoice = {
  id: string;
  invoice_id: string;
  customer_name: string | null;
  customer_email: string;
  amount_due_cents: number;
  raw_decline_code: string;
  iso_8583_code: string | null;
  failure_type: string | null;
  status: string;
  attempt_count: number;
  next_action_scheduled_at: string | null;
  recovered_at: string | null;
  created_at: string;
};

export type DashboardSummary = {
  revenue_at_risk_cents: number;
  revenue_recovered_cents: number;
  revenue_exhausted_cents: number;
  recovery_rate: number | null;
  top_failure_reasons: { reason: string; count: number }[];
  pipeline_counts: Record<string, number>;
  recent_actions: {
    invoice_id: string;
    action_type: string;
    channel: string | null;
    is_successful: boolean | null;
    created_at: string;
  }[];
};

export type PortalInvoice = {
  already_recovered: boolean;
  tenant_name: string;
  customer_name?: string;
  amount_due_cents?: number;
  currency?: string;
  invoice_ref?: string;
};

export type ModelStatus = {
  trained: boolean;
  enabled: boolean;
  active: boolean;
  is_synthetic?: boolean;
  trained_at?: string;
  n_samples?: number;
  test_auc?: number;
  test_accuracy?: number;
  test_brier_score?: number;
};

export type ActivityAction = {
  id: string;
  action_type: string;
  channel: string | null;
  is_successful: boolean | null;
  created_at: string;
  invoice_ref: string | null;
  customer_name: string | null;
  amount_due_cents: number | null;
};

export type CopilotResponse = {
  question: string;
  sql: string;
  columns: string[];
  rows: unknown[][];
  answer: string;
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`Request to ${path} failed (${res.status}): ${detail}`);
  }
  return res.json();
}

export const api = {
  getSummary: () => request<DashboardSummary>("/dashboard/summary"),
  getInvoices: (status?: string) =>
    request<Invoice[]>(`/invoices${status ? `?status=${status}` : ""}`),
  runRecoveryCycle: () => request<{ ran_at: string; result: Record<string, number> }>(
    "/invoices/run-recovery-cycle",
    { method: "POST" }
  ),
  askCopilot: (question: string) =>
    request<CopilotResponse>("/copilot/ask", {
      method: "POST",
      body: JSON.stringify({ question }),
    }),
  getPortalInvoice: (token: string) =>
    request<PortalInvoice>(`/portal/invoice?token=${encodeURIComponent(token)}`),
  updateCard: (token: string) =>
    request<{ status: string }>("/portal/update-card", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),
  getModelStatus: () => request<ModelStatus>("/model/status"),
  getActivity: (limit = 15) =>
    request<ActivityAction[]>(`/invoices/actions?limit=${limit}`),
};

export function formatCents(cents: number): string {
  return (cents / 100).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

import { api, ActivityAction, DashboardSummary, Invoice, ModelStatus, PortalInvoice } from "@/lib/api";
import {
  demoActivity,
  demoInvoices,
  demoModelStatus,
  demoPortalInvoice,
  demoSummary,
} from "@/lib/demo-data";

export const USE_DUMMY_DATA = true;

export const dataSource = {
  getSummary: async (): Promise<DashboardSummary> =>
    USE_DUMMY_DATA ? demoSummary : api.getSummary(),
  getInvoices: async (status?: string): Promise<Invoice[]> => {
    if (!USE_DUMMY_DATA) return api.getInvoices(status);
    return status ? demoInvoices.filter((invoice) => invoice.status === status) : demoInvoices;
  },
  getModelStatus: async (): Promise<ModelStatus> =>
    USE_DUMMY_DATA ? demoModelStatus : api.getModelStatus(),
  getActivity: async (limit = 15): Promise<ActivityAction[]> =>
    USE_DUMMY_DATA ? demoActivity.slice(0, limit) : api.getActivity(limit),
  runRecoveryCycle: async () =>
    USE_DUMMY_DATA
      ? { ran_at: new Date().toISOString(), result: { demo: 1 } }
      : api.runRecoveryCycle(),
  getPortalInvoice: async (token: string): Promise<PortalInvoice> =>
    USE_DUMMY_DATA && token === "demo"
      ? demoPortalInvoice
      : api.getPortalInvoice(token),
  updateCard: async (token: string) =>
    USE_DUMMY_DATA && token === "demo" ? { status: "updated" } : api.updateCard(token),
};
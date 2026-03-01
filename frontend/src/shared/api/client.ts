import axios from "axios";

export const api = axios.create({
  // Default to same-origin paths so Vite dev proxy can forward /api to backend.
  // For non-proxied deployments, set VITE_API_BASE_URL explicitly.
  baseURL: import.meta.env.VITE_API_BASE_URL || "/",
  timeout: 30000
});

export type SearchItem = {
  paper_uid: string;
  source: string;
  external_id: string;
  title: string;
  authors: string[];
  abstract?: string;
  pdf_url?: string | null;
  pdf_unavailable: boolean;
};

export type PaperListItem = {
  paper_uid: string;
  source: string;
  external_id: string;
  doi?: string | null;
  title: string;
  authors: string[];
  abstract?: string | null;
  published_at?: string | null;
  source_url?: string | null;
  pdf_unavailable: boolean;
  recommended_count: number;
  has_pdf: boolean;
  pdf_url?: string | null;
  keywords: string[];
  liked: boolean;
};

export type PaperDetail = PaperListItem & {
  analysis: Record<string, unknown> | null;
  analysis_created_at?: string | null;
};

export type DailyReport = {
  report_id: string;
  report_date: string;
  summary_md: string;
  paper_uids: string[];
  meta?: Record<string, unknown>;
  created_at?: string;
};

export type ResearchTaskItem = {
  task_id: string;
  topic: string;
  status: string;
  started_at?: string | null;
  finished_at?: string | null;
  error_message?: string | null;
};

export type SystemStatus = {
  system_time: string;
  timezone: string;
  paper_count: number;
  daily_report_count: number;
  research_task_count: number;
  job_count: number;
  liked_paper_count: number;
  service_health: Record<string, boolean>;
};

export type SourceAvailability = {
  overall_ok: boolean;
  window_days: number;
  start_date: string;
  end_date: string;
  sources: Record<string, { ok: boolean; reason: string; count: number; sample_external_id?: string | null }>;
};

export async function searchPapers(payload: {
  sources: string[];
  keywords: string[];
  page?: number;
  page_size?: number;
}) {
  const { data } = await api.post("/api/v1/papers/search", payload);
  return data;
}

export async function listPapers(payload?: { page?: number; page_size?: number }) {
  const { data } = await api.get("/api/v1/papers", { params: payload });
  return data as { items: PaperListItem[]; total: number; page: number; page_size: number };
}

export async function getPaperDetail(paperUid: string) {
  const { data } = await api.get(`/api/v1/papers/${paperUid}`);
  return data as PaperDetail;
}

export async function sendPaperInteraction(payload: { paper_uid: string; action: string; note?: string }) {
  const { data } = await api.post("/api/v1/interactions", payload);
  return data;
}

export async function importPaper(payload: { source: string; external_id: string; pdf_url?: string | null }) {
  const { data } = await api.post("/api/v1/papers/import", payload);
  return data;
}

export async function generateRecommendations(payload: { paper_uids: string[]; top_k: number }) {
  const { data } = await api.post("/api/v1/recommendations/generate", payload);
  return data;
}

export async function createResearchTask(payload: { topic: string; constraints: Record<string, string> }) {
  const { data } = await api.post("/api/v1/research/tasks", payload);
  return data;
}

export async function listResearchTasks(limit = 50) {
  const { data } = await api.get("/api/v1/research/tasks", { params: { limit } });
  return data as { items: ResearchTaskItem[] };
}

export async function getResearchResult(taskId: string) {
  const { data } = await api.get(`/api/v1/research/tasks/${taskId}/result`);
  return data;
}

export async function generateDailyReport(payload: {
  report_date: string;
  sources: string[];
  keywords: string[];
  arxiv_categories?: string[];
  window_days?: number;
  top_k: number;
}) {
  const { data } = await api.post("/api/v1/reports/daily/generate", payload);
  return data;
}

export async function generateDailyReportAsync(payload: {
  report_date: string;
  sources: string[];
  keywords: string[];
  arxiv_categories?: string[];
  window_days?: number;
  top_k: number;
}) {
  const { data } = await api.post("/api/v1/reports/daily/generate-async", payload);
  return data as { job_id: string; trace_id: string; status: string };
}

export async function getDailyReport(reportId: string) {
  const { data } = await api.get(`/api/v1/reports/daily/${reportId}`);
  return data as DailyReport;
}

export async function getDailyReportByDate(reportDate: string) {
  const { data } = await api.get(`/api/v1/reports/daily/by-date/${reportDate}`);
  return data as DailyReport;
}

export async function getSettings() {
  const { data } = await api.get("/api/v1/settings");
  return data as Record<string, unknown>;
}

export async function updateSettings(payload: Record<string, unknown>) {
  const { data } = await api.put("/api/v1/settings", payload);
  return data as Record<string, unknown>;
}

export async function getSystemStatus() {
  const { data } = await api.get("/api/v1/system/status");
  return data as SystemStatus;
}

export async function getSourceAvailability(windowDays = 7) {
  const { data } = await api.get("/api/v1/sources/availability", { params: { window_days: windowDays } });
  return data as SourceAvailability;
}

export async function getTask(jobId: string) {
  const { data } = await api.get(`/api/v1/tasks/${jobId}`);
  return data;
}

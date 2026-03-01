import axios from "axios";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001",
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

export async function searchPapers(payload: {
  sources: string[];
  keywords: string[];
  page?: number;
  page_size?: number;
}) {
  const { data } = await api.post("/api/v1/papers/search", payload);
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

export async function getResearchResult(taskId: string) {
  const { data } = await api.get(`/api/v1/research/tasks/${taskId}/result`);
  return data;
}

export async function generateDailyReport(payload: {
  report_date: string;
  sources: string[];
  keywords: string[];
  top_k: number;
}) {
  const { data } = await api.post("/api/v1/reports/daily/generate", payload);
  return data;
}

export async function getDailyReport(reportId: string) {
  const { data } = await api.get(`/api/v1/reports/daily/${reportId}`);
  return data;
}

export async function getSettings() {
  const { data } = await api.get("/api/v1/settings");
  return data;
}

export async function updateSettings(payload: Record<string, unknown>) {
  const { data } = await api.put("/api/v1/settings", payload);
  return data;
}

export async function getTask(jobId: string) {
  const { data } = await api.get(`/api/v1/tasks/${jobId}`);
  return data;
}

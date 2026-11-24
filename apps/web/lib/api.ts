/** Typed fetch layer. Server components call the API directly; the browser uses the same-origin /api proxy. */
import { apiBase } from "./config";
import type {
  AgentVersionOut, AnnotationSummary, BlindItem, CaseComparison, ComparisonDetail, ComparisonOut, DatasetDetail,
  DatasetVersionOut, FailuresResp, GateOut, JudgeOut, Meta, Overview, RunDetail, RunList, SampleDetail, SampleList, TraceOut,
} from "./types";

export type ApiErrorKind = "not_found" | "forbidden" | "rate_limited" | "conflict" | "server" | "network" | "client";

export class ApiError extends Error {
  constructor(public kind: ApiErrorKind, public status: number, message: string) {
    super(message);
  }
}

const isServer = typeof window === "undefined";
const base = () => (isServer ? apiBase() : "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${base()}${path}`, { cache: "no-store", ...init, headers: { "content-type": "application/json", ...init?.headers } });
  } catch {
    throw new ApiError("network", 0, "The API could not be reached. Is the backend running?");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = ((await res.json()) as { detail?: string }).detail ?? detail; } catch { /* non-JSON error body */ }
    const kind: ApiErrorKind = res.status === 404 ? "not_found" : res.status === 403 || res.status === 401 ? "forbidden"
      : res.status === 429 ? "rate_limited" : res.status === 409 ? "conflict" : res.status >= 500 ? "server" : "client";
    throw new ApiError(kind, res.status, detail);
  }
  return (await res.json()) as T;
}

const qs = (o: Record<string, string | number | undefined | null>) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(o)) if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const api = {
  meta: () => request<Meta>("/api/meta"),
  overview: () => request<Overview>("/api/overview"),
  agents: () => request<AgentVersionOut[]>("/api/agents"),
  datasets: () => request<DatasetVersionOut[]>("/api/datasets"),
  dataset: (name: string, version: string) => request<DatasetDetail>(`/api/datasets/${name}/${version}`),
  candidates: () => request<{ id: number; status: string; case: Record<string, unknown>; created_at: string }[]>("/api/candidates"),
  runs: (q: Record<string, string | number | undefined> = {}) => request<RunList>(`/api/runs${qs(q)}`),
  run: (id: string) => request<RunDetail>(`/api/runs/${id}`),
  samples: (id: string, q: Record<string, string | number | undefined> = {}) => request<SampleList>(`/api/runs/${id}/samples${qs(q)}`),
  sample: (id: number) => request<SampleDetail>(`/api/samples/${id}`),
  trace: (id: number) => request<TraceOut>(`/api/samples/${id}/trace`),
  traces: (q: Record<string, string | number | undefined> = {}) =>
    request<{ page: number; total: number; items: SampleList["items"] }>(`/api/traces${qs(q)}`),
  comparisons: () => request<ComparisonOut[]>("/api/comparisons"),
  comparison: (id: number) => request<ComparisonDetail>(`/api/comparisons/${id}`),
  caseComparison: (id: number, caseId: string) => request<CaseComparison>(`/api/comparisons/${id}/cases/${caseId}`),
  gates: () => request<GateOut[]>("/api/gates"),
  policies: () => request<Record<string, { min_cases: number; alpha: number; n_boot: number; margin: number }>>("/api/policies"),
  failures: (runId: string, baseline?: string) => request<FailuresResp>(`/api/failures${qs({ run_id: runId, baseline_run_id: baseline })}`),
  judges: () => request<JudgeOut[]>("/api/judges"),
  calibrationItems: (runId: number) =>
    request<{ items: { item_id: string; input: string; candidate_output: string; reference_label: boolean; label_source: string; predicted: boolean; notes: string }[]; errors: unknown[] }>(
      `/api/calibration/${runId}/items`),
  annotationSummary: () => request<AnnotationSummary>("/api/annotation/summary"),
  annotationNext: (annotator: string) => request<BlindItem | null>(`/api/annotation/next${qs({ annotator })}`),
  annotationProgress: (annotator: string) =>
    request<{ total: number; labelled: number; skipped: number }>(`/api/annotation/progress${qs({ annotator })}`),
  annotate: (body: { item_id: string; annotator: string; label: boolean | null; note?: string }) =>
    request<{ ok: boolean }>("/api/annotation", { method: "POST", body: JSON.stringify(body) }),
  adjudicate: (body: { item_id: string; adjudicator: string; label: boolean; note?: string }) =>
    request<{ ok: boolean }>("/api/annotation/adjudicate", { method: "POST", body: JSON.stringify(body) }),
};

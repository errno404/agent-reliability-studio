import type { components } from "./api-types";

type S = components["schemas"];
export type Meta = S["Meta"];
export type RunOut = S["RunOut"];
export type RunDetail = S["RunDetail"];
export type RunList = S["RunList"];
export type SampleOut = S["SampleOut"];
export type SampleList = S["SampleList"];
export type SampleDetail = S["SampleDetail"];
export type AssertionOut = S["AssertionOut"];
export type TraceOut = S["TraceOut"];
export type SpanOut = S["SpanOut"];
export type ComparisonOut = S["ComparisonOut"];
export type ComparisonDetail = S["ComparisonDetail"];
export type CaseComparison = S["CaseComparison"];
export type GateOut = S["GateOut"];
export type JudgeOut = S["JudgeOut"];
export type BlindItem = S["BlindItem"];
export type DatasetVersionOut = S["DatasetVersionOut"];
export type DatasetDetail = S["DatasetDetail"];
export type AgentVersionOut = S["AgentVersionOut"];

// Free-form JSON sections (typed here because OpenAPI exposes them as open objects).
export interface Rate { rate: number | null; n: number; passed: number; ci_low: number; ci_high: number }
export interface Summary {
  n_samples: number; n_cases: number; status_counts: Record<string, number>;
  task_success: Rate; outcome: Rate; trajectory: Rate; component: Rate; policy: Rate;
  execution_error_rate: number; latency_p50_ms: number; latency_p95_ms: number;
  total_tokens: number; input_tokens: number; output_tokens: number; cost_usd: number | null; cost_label: string;
  pass_hat_k: number; pass_at_k: number; k: number; single_run_pass_rate: number; single_run_ci: [number, number];
  flaky_cases: string[]; flips_by_category: Record<string, number>; failure_labels: Record<string, number>;
}
export interface Cluster {
  label: string; count: number; pct_of_failures: number; severity: string; categories: Record<string, number>;
  example_sample_ids: number[]; summary: string; source: string;
}
export interface TrendPoint { agent: string; version: string; run_id: string; rate: number; ci_low: number; ci_high: number; n: number; pass_hat_k: number; pass_at_k: number }
export interface CategoryDelta { baseline: number | null; candidate: number | null; delta: number | null; n_baseline: number; n_candidate: number }
export interface Overview {
  empty: boolean; headline: ComparisonOut; baseline: RunOut; candidate: RunOut;
  gate: { verdict: string; reasons: string[] } | null;
  kpis: { candidate: Summary; baseline: Summary };
  what_changed: string; category_deltas: Record<string, CategoryDelta>;
  trend: TrendPoint[]; failure_categories: Cluster[]; baseline_failure_categories: Cluster[];
  recent_runs: RunOut[]; totals: { runs: number; samples: number; comparisons: number };
}
export interface Bootstrap {
  decision: string; delta: number; ci_low: number; ci_high: number; n_common_cases: number; n_improved: number;
  n_regressed: number; n_unchanged: number; baseline_rate: number; candidate_rate: number; reason: string;
}
export interface CaseChange {
  case_id: string; baseline: number; candidate: number; delta: number; kind: "improved" | "regressed"; category: string;
  trajectory_diff?: TrajDiff;
}
export interface TrajDiff {
  baseline: string[]; candidate: string[]; identical: boolean; added_tools: string[]; removed_tools: string[];
  changed_arguments: { tool: string; baseline: Record<string, unknown>; candidate: Record<string, unknown> }[];
  latency_delta_ms: number; token_delta: number; cost_delta: number | null;
  ops: { op: string; tool?: string; baseline?: string[]; candidate?: string[] }[];
  changed_outcome?: boolean; baseline_status?: string; candidate_status?: string;
  assertions_newly_failing?: string[]; assertions_fixed?: string[];
}
export interface ComparisonResult {
  bootstrap: Bootstrap | null; mcnemar: { b: number; c: number; p_value: number; note: string } | null;
  baseline_summary: Summary; candidate_summary: Summary; category_deltas: Record<string, CategoryDelta>;
  case_changes: CaseChange[]; new_failure_labels: Record<string, number>; what_changed: string;
}
export interface Validity { valid: boolean; reasons: string[]; warnings: string[]; mode: string }
export interface CalMetrics { n: number; n_pos: number; n_neg: number; tp: number; fp: number; tn: number; fn: number; accuracy: number; precision: number; recall: number; f1: number; kappa: number; fpr: number; fnr: number }
export interface CalRun { id: number; n_items_used: number; admitted: boolean; reasons: string[]; metrics: CalMetrics; policy: Record<string, number | string>; reference_sources: Record<string, number>; created_at: string; set_id: number }
export interface FailuresResp {
  run: RunOut; n_failed_samples: number; n_execution_errors: number; total_labels: number; summary: string; note: string;
  clusters: (Cluster & { baseline_count: number; delta: number; increased: boolean; new: boolean; examples: SampleOut[] })[];
}
export interface AnnotationSummary {
  annotators: string[]; n_labels: number; kappa: number | null; items_compared: number; sources: string[];
  consensus_claimed: boolean; note: string;
  disagreement_queue: { item_id: string; labels: Record<string, boolean>; input: string; candidate_output: string; rubric: { must?: string[]; must_not?: string[] }; adjudicated: boolean }[];
}
export interface CaseDef {
  id: string; title: string; category: string; description: string; input: string; assertions: { type: string; layer: string; gating?: boolean; [k: string]: unknown }[];
  rubric?: Record<string, unknown>; budgets?: Record<string, unknown>; trajectory?: Record<string, unknown>; fixture?: Record<string, unknown>;
  simulated_user?: Record<string, unknown>; severity?: string; tags?: string[];
}

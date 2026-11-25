import type { CalRun, ComparisonOut, RunOut } from "./types";

/** Live (real model) vs synthetic (scripted, seeded) runs are NEVER blended: every aggregate is computed per kind. */
export type Kind = "live" | "synthetic";
export const kindOf = (r: Pick<RunOut, "execution_kind">): Kind => (r.execution_kind === "live" ? "live" : "synthetic");
export const isLive = (r: Pick<RunOut, "execution_kind">): boolean => kindOf(r) === "live";

export function splitKinds(runs: RunOut[]): Record<Kind, { runs: number; samples: number }> {
  const out = { live: { runs: 0, samples: 0 }, synthetic: { runs: 0, samples: 0 } };
  for (const r of runs) { out[kindOf(r)].runs += 1; out[kindOf(r)].samples += r.n_samples; }
  return out;
}

/** Comparison list items carry no execution kind; derive it from the two runs (a mixed pair is flagged, never silently merged). */
export function comparisonKind(c: Pick<ComparisonOut, "baseline_run_id" | "candidate_run_id">, runs: RunOut[]): Kind | "mixed" {
  const by = new Map(runs.map((r) => [r.id, kindOf(r)]));
  const a = by.get(c.baseline_run_id), b = by.get(c.candidate_run_id);
  return a && b && a === b ? a : a || b ? "mixed" : "synthetic";
}

export const kindLabel = (k: Kind | "mixed"): string => (k === "live" ? "LIVE · real model" : k === "mixed" ? "MIXED KINDS" : "SYNTHETIC");
export const LIVE_NOTE = "Real LLM behaviour evaluated in a controlled synthetic environment.";

/** What each comparison intent is ALLOWED to vary (mirrors evalcore.manifest.INTENTS); everything else must match. */
export const INTENT_VARIES: Record<string, string[]> = {
  prompt_change: [], agent_change: [], model_change: ["model", "model_resolved", "model_params"],
  tool_change: ["tool_schema_hash"], evaluator_change: ["evaluator_hash", "evaluator_config_hash", "rubric_hash", "judge_*"],
};
export const ALWAYS_CONTROLLED = ["dataset_name", "dataset_hash", "fixture_hash", "samples_per_case", "execution_kind", "model_provider", "simulated_user_model", "simulated_user_prompt_hash"];
export function controlledVariables(intent: string): { varied: string[]; controlled: string[] } {
  const varied = INTENT_VARIES[intent] ?? [];
  const all = [...ALWAYS_CONTROLLED, "model", "model_resolved", "model_params", "tool_schema_hash", "evaluator_hash", "evaluator_config_hash", "rubric_hash", "judge_backend", "judge_model", "judge_prompt_hash"];
  return { varied, controlled: all.filter((x) => !varied.some((v) => v === x || (v.endsWith("*") && x.startsWith(v.slice(0, -1))))) };
}
export const intentLabel = (i: string): string => i.replace(/_/g, " ");
/** `strict` is the only mode that can authorise a release; anything else is research/diagnostic. */
export const modeLabel = (mode: string, authorization?: string): { text: string; tone: "ok" | "warn" } =>
  mode === "strict" ? { text: authorization ? `STRICT · ${authorization}` : "STRICT", tone: "ok" } : { text: `${mode.toUpperCase()} · diagnostic only, cannot authorise a release`, tone: "warn" };

/** 95% Wilson interval (same formula as evalcore.stats.wilson_interval). */
export function wilson(successes: number, n: number, z = 1.959963984540054): [number, number] {
  if (n <= 0) return [0, 1];
  const p = successes / n, d = 1 + (z * z) / n;
  const c = (p + (z * z) / (2 * n)) / d, h = (z * Math.sqrt((p * (1 - p)) / n + (z * z) / (4 * n * n))) / d;
  return [Math.max(0, c - h), Math.min(1, c + h)];
}

const TRUSTED = ["human", "adjudicated"];
export interface ReleaseScope { eligible: boolean; scope: "release" | "demonstration" | "diagnostic"; reasons: string[]; fprUpper: number | null; nNegatives: number; trusted: number }
/** Mirrors evalcore.calibration.release_eligibility using the policy STORED with the calibration (the API does not expose it yet). */
export function releaseScope(latest: CalRun | null): ReleaseScope {
  if (!latest) return { eligible: false, scope: "diagnostic", reasons: ["never calibrated"], fprUpper: null, nNegatives: 0, trusted: 0 };
  const m = latest.metrics, pol = latest.policy;
  const nNeg = m.fp + m.tn;
  const ub = nNeg ? wilson(m.fp, nNeg)[1] : 1;
  const trusted = TRUSTED.reduce((a, k) => a + (latest.reference_sources[k] ?? 0), 0);
  const minTrusted = Number(pol.min_trusted_items ?? 50), maxUpper = Number(pol.max_fpr_upper ?? 0.1);
  const why: string[] = [];
  if (!latest.admitted) why.push("not admitted by the standard policy");
  if (trusted < minTrusted) why.push(`${trusted} human/adjudicated reference labels (release needs ≥ ${minTrusted}); ${latest.reference_sources.synthetic_fixture ?? 0} are synthetic fixtures`);
  if (ub > maxUpper) why.push(`95% upper bound on the false-positive rate is ${(ub * 100).toFixed(1)}% (release needs ≤ ${(maxUpper * 100).toFixed(0)}%) from ${nNeg} negatives`);
  return { eligible: why.length === 0, scope: why.length === 0 ? "release" : latest.admitted ? "demonstration" : "diagnostic", reasons: why, fprUpper: ub, nNegatives: nNeg, trusted };
}
export const scopeLabel = (s: ReleaseScope["scope"]): string =>
  s === "release" ? "RELEASE-ELIGIBLE" : s === "demonstration" ? "DEMONSTRATION ONLY — cannot authorise a release" : "DIAGNOSTIC ONLY";

/** Annotation provenance. Only authenticated 'human' rows are evidence; anonymous public handles are crowd input. */
export function annotationTrust(source: string | undefined): { label: string; tone: "ok" | "warn" | "neutral"; title: string } {
  if (source === "public_untrusted") return { label: "untrusted · public handle", tone: "warn", title: "Anonymous, unauthenticated handle. Never counts as calibration evidence or toward a consensus claim." };
  if (source === "human") return { label: "trusted · authenticated", tone: "ok", title: "Authenticated human annotation (admin workflow)." };
  if (source === "synthetic_demo") return { label: "synthetic demo annotator", tone: "neutral", title: "Seeded stand-in, not a human." };
  return { label: source ?? "unknown", tone: "neutral", title: "" };
}

export const PROOF_RUNS = [
  { n: 1, what: "Compatible candidate reaches the real baseline/candidate comparison", outcome: "pass", url: "https://github.com/errno404/agent-reliability-studio/actions/runs/45522330283" },
  { n: 2, what: "Deliberately regressed candidate is rejected", outcome: "rejected", url: "https://github.com/errno404/agent-reliability-studio/actions/runs/45522334340" },
  { n: 3, what: "Invalid comparison (undeclared model change) is rejected", outcome: "rejected", url: "https://github.com/errno404/agent-reliability-studio/actions/runs/45522338959" },
  { n: 4, what: "Edit of a frozen agent version (with a rewritten pin) is rejected", outcome: "rejected", url: "https://github.com/errno404/agent-reliability-studio/actions/runs/45522337133" },
] as const;
export const EXPERIMENT_REPORT_PATH = "docs/experiments/001-research-agent-reliability.md";

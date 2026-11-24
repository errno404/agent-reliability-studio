export const pct = (v: number | null | undefined, digits = 1): string => (v === null || v === undefined ? "—" : `${(v * 100).toFixed(digits)}%`);

/** Signed percentage-point delta, e.g. +12.3 pts. */
export const pts = (v: number | null | undefined, digits = 1): string =>
  v === null || v === undefined ? "—" : `${v >= 0 ? "+" : "−"}${Math.abs(v * 100).toFixed(digits)} pts`;

export const ms = (v: number): string => (v >= 1000 ? `${(v / 1000).toFixed(2)} s` : `${Math.round(v)} ms`);
export const num = (v: number): string => new Intl.NumberFormat("en-US").format(Math.round(v));
export const usd = (v: number | null | undefined): string => (v === null || v === undefined ? "—" : `$${v < 1 ? v.toFixed(4) : v.toFixed(2)}`);
export const ci = (lo: number, hi: number): string => `${(lo * 100).toFixed(1)}–${(hi * 100).toFixed(1)}%`;
export const shortDate = (iso: string): string => new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
export const label = (s: string): string => s.replace(/_/g, " ");

export type Tone = "ok" | "warn" | "bad" | "info" | "neutral";
export const decisionTone = (d: string): Tone =>
  ({ significant_improvement: "ok", no_meaningful_regression: "ok", significant_regression: "bad", inconclusive: "warn", invalid: "info" } as Record<string, Tone>)[d] ?? "neutral";
export const decisionLabel = (d: string): string =>
  ({ significant_improvement: "IMPROVEMENT", no_meaningful_regression: "PASS · no meaningful regression", significant_regression: "REGRESSION",
     inconclusive: "INCONCLUSIVE", invalid: "INVALID COMPARISON" } as Record<string, string>)[d] ?? d.toUpperCase();
export const statusTone = (s: string): Tone =>
  ({ passed: "ok", succeeded: "ok", failed: "bad", execution_error: "warn", invalid: "info", skipped: "neutral", running: "info", queued: "neutral" } as Record<string, Tone>)[s] ?? "neutral";
export const statusLabel = (s: string): string => ({ execution_error: "execution error" } as Record<string, string>)[s] ?? s;

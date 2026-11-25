import Link from "next/link";
import { CiPlot } from "@/components/charts";
import { Badge, Card, CardHeader, DecisionBadge, HashChip, KindBadge } from "@/components/ui";
import { ms, num, pct, pts } from "@/lib/format";
import type { ComparisonDetail, ComparisonResult, Summary } from "@/lib/types";

/** Every number here is read from the API response (a comparison recomputed by the evaluator from stored samples). */
export function ExperimentCard({ comp, title }: { comp: ComparisonDetail; title: string }) {
  const r = comp.result as unknown as ComparisonResult;
  const b = r.baseline_summary as Summary, c = r.candidate_summary as Summary, boot = r.bootstrap;
  const rows: [string, string, string][] = [
    ["Task success (mean of trials)", `${pct(b.task_success.rate)} · ${b.task_success.passed}/${b.task_success.n}`, `${pct(c.task_success.rate)} · ${c.task_success.passed}/${c.task_success.n}`],
    ["pass^k / pass@k", `${pct(b.pass_hat_k, 0)} / ${pct(b.pass_at_k, 0)} (k=${b.k})`, `${pct(c.pass_hat_k, 0)} / ${pct(c.pass_at_k, 0)} (k=${c.k})`],
    ["Eligible cases", `${b.eligible_cases ?? b.n_cases} of ${b.n_cases}`, `${c.eligible_cases ?? c.n_cases} of ${c.n_cases}`],
    ["Execution success", pct(b.execution_success_rate), pct(c.execution_success_rate)],
    ["Latency p50 / p95", `${ms(b.latency_p50_ms)} / ${ms(b.latency_p95_ms)}`, `${ms(c.latency_p50_ms)} / ${ms(c.latency_p95_ms)}`],
    ["Tokens (in+out)", num(b.total_tokens), num(c.total_tokens)],
  ];
  return (
    <Card aria-label={title}>
      <CardHeader title={title} sub={<span className="flex flex-wrap items-center gap-1.5"><Badge>{comp.baseline_label}</Badge>→<Badge tone="info">{comp.candidate_label}</Badge><span>intent: {comp.intent.replace(/_/g, " ")}</span><span>· {comp.mode}</span></span>} right={<span className="flex flex-wrap items-center gap-2"><KindBadge kind="live" /><DecisionBadge decision={comp.decision} /></span>} />
      <div className="space-y-4 p-4">
        <p className="text-[14px]">{comp.explanation}</p>
        {boot ? (
          <div className="grid gap-4 lg:grid-cols-2">
            <div>
              <CiPlot delta={boot.delta} lo={boot.ci_low} hi={boot.ci_high} margin={comp.margin ?? 0.05} />
              <p className="num mt-1 text-xs text-muted">Δ {pts(boot.delta)} · 95% CI [{pts(boot.ci_low)}, {pts(boot.ci_high)}] · {boot.n_common_cases} matched cases · {boot.n_improved} improved / {boot.n_regressed} regressed / {boot.n_unchanged} unchanged · case-clustered bootstrap</p>
              {boot.ci_low <= 0 && boot.decision !== "significant_regression" && <p className="mt-1 text-xs text-muted">The interval includes zero: this is a one-sided non-inferiority result, <b>not</b> a demonstrated improvement and not a claim of equivalence.</p>}
            </div>
            <div className="scroll-x"><table className="w-full min-w-[420px] text-[13px]"><thead className="border-b border-line text-[11px] uppercase tracking-wider text-faint"><tr><th className="px-2 py-1.5 text-left font-medium">Metric</th><th className="px-2 py-1.5 text-left font-medium">Baseline</th><th className="px-2 py-1.5 text-left font-medium">Candidate</th></tr></thead>
              <tbody className="divide-y divide-line">{rows.map(([k, x, y]) => <tr key={k}><th scope="row" className="px-2 py-1.5 text-left font-medium">{k}</th><td className="num px-2 py-1.5">{x}</td><td className="num px-2 py-1.5">{y}</td></tr>)}</tbody></table></div>
          </div>
        ) : <p className="rounded border border-info/30 bg-info-soft px-3 py-2 text-sm">No statistics were computed: this comparison is {comp.valid ? "incomplete" : "invalid"}. {(comp.validity as { reasons?: string[] }).reasons?.[0] ?? ""}</p>}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <HashChip label="dataset" value={comp.baseline.dataset_hash} />
          <Link className="text-accent hover:underline" href={`/compare/${comp.id}`}>Full comparison →</Link>
          <Link className="text-accent hover:underline" href={`/experiments/${comp.baseline.id}`}>baseline run</Link>
          <Link className="text-accent hover:underline" href={`/experiments/${comp.candidate.id}`}>candidate run</Link>
        </div>
      </div>
    </Card>
  );
}

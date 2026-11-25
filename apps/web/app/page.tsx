import Link from "next/link";
import { CategoryDeltaBars, CiPlot, FailureBars, TrendChart } from "@/components/charts";
import { Ledger, type LedgerRow } from "@/components/ledger";
import { Badge, Card, CardHeader, DecisionBadge, EmptyState, ErrorState, KindBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { ms, num, pct, pts, usd } from "@/lib/format";
import { comparisonKind, splitKinds } from "@/lib/live";
import type { ComparisonDetail, ComparisonResult, Overview, Rate, Summary } from "@/lib/types";

export const dynamic = "force-dynamic";

type Sm = Overview["kpis"]["candidate"];
function ledgerRows(c: Sm, b: Sm): LedgerRow[] {
  const rate = (label: string, r: Rate, br: Rate): LedgerRow => ({ label, base: pct(br.rate), cand: pct(r.rate), delta: r.rate !== null && br.rate !== null ? r.rate - br.rate : null, note: `n=${r.n} · 95% CI ${pct(r.ci_low, 0)}–${pct(r.ci_high, 0)}` });
  return [
    rate("Task success", c.task_success, b.task_success),
    rate("Outcome", c.outcome, b.outcome),
    rate("Trajectory", c.trajectory, b.trajectory),
    rate("Tool / component", c.component, b.component),
    rate("Policy / safety", c.policy, b.policy),
    { label: "pass^k (every repeat passes)", base: pct(b.pass_hat_k, 0), cand: pct(c.pass_hat_k, 0), delta: c.pass_hat_k - b.pass_hat_k, note: `k=${c.k}` },
    { label: "pass@k (any repeat passes)", base: pct(b.pass_at_k, 0), cand: pct(c.pass_at_k, 0), delta: c.pass_at_k - b.pass_at_k, note: `k=${c.k}` },
    { label: "Execution errors", base: pct(b.execution_error_rate), cand: pct(c.execution_error_rate), delta: c.execution_error_rate - b.execution_error_rate, invert: true, note: "excluded from quality rates" },
    { label: "Latency p50 / p95", base: `${ms(b.latency_p50_ms)} / ${ms(b.latency_p95_ms)}`, cand: `${ms(c.latency_p50_ms)} / ${ms(c.latency_p95_ms)}`, note: "virtual clock" },
    { label: "Tokens in + out", base: num(b.total_tokens), cand: num(c.total_tokens) },
    { label: "API-equivalent cost", base: usd(b.cost_usd), cand: usd(c.cost_usd), note: "synthetic price table" },
  ];
}

/** The answer to the product question, from the latest valid real-model comparison. Every number is read from the API. */
function LiveVerdict({ comp }: { comp: ComparisonDetail }) {
  const r = comp.result as unknown as ComparisonResult;
  const bs = r.baseline_summary as Summary, cs = r.candidate_summary as Summary, boot = r.bootstrap;
  const rows: LedgerRow[] = [
    { label: "Task success", base: pct(bs.task_success.rate), cand: pct(cs.task_success.rate), delta: (cs.task_success.rate ?? 0) - (bs.task_success.rate ?? 0), note: `${cs.task_success.passed}/${cs.task_success.n} trials` },
    { label: "pass^k (every repeat passes)", base: pct(bs.pass_hat_k, 0), cand: pct(cs.pass_hat_k, 0), delta: cs.pass_hat_k - bs.pass_hat_k, note: `k=${cs.k}` },
    { label: "pass@k (any repeat passes)", base: pct(bs.pass_at_k, 0), cand: pct(cs.pass_at_k, 0), delta: cs.pass_at_k - bs.pass_at_k, note: `k=${cs.k}` },
    { label: "Execution success", base: pct(bs.execution_success_rate), cand: pct(cs.execution_success_rate), delta: (cs.execution_success_rate ?? 0) - (bs.execution_success_rate ?? 0) },
    { label: "Latency p50 / p95", base: `${ms(bs.latency_p50_ms)} / ${ms(bs.latency_p95_ms)}`, cand: `${ms(cs.latency_p50_ms)} / ${ms(cs.latency_p95_ms)}` },
    { label: "Tokens in + out", base: num(bs.total_tokens), cand: num(cs.total_tokens) },
  ];
  return (
    <section aria-labelledby="verdict" className="space-y-4">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] text-muted">
        <KindBadge kind="live" />
        <span id="verdict" className="font-medium text-fg">Latest experiment: {comp.name}</span>
        <span className="mono text-[12px]">{comp.baseline_label} → {comp.candidate_label}</span>
        <span>intent: {comp.intent.replace(/_/g, " ")} · {comp.mode}</span>
      </div>
      <div className="grid grid-cols-1 gap-x-10 gap-y-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2"><DecisionBadge decision={comp.decision} />{comp.gate_verdict && <Badge tone={comp.gate_verdict === "pass" ? "ok" : "bad"}>gate: {comp.gate_verdict}</Badge>}</div>
          <p className="max-w-[62ch] text-[17px] leading-snug tracking-tight">{comp.explanation}</p>
          {boot && boot.ci_low <= 0 && <p className="max-w-[62ch] text-[13px] text-muted">The interval includes zero. This supports “no meaningful regression”, not a demonstrated improvement.</p>}
          <p className="text-[12.5px] text-muted">Real model decisions in a controlled synthetic environment. <Link className="text-accent hover:underline" href={`/compare/${comp.id}`}>Open the comparison</Link> · <Link className="text-accent hover:underline" href="/experiments">All live experiments</Link></p>
        </div>
        <div className="space-y-2">
          {boot && <CiPlot delta={boot.delta} lo={boot.ci_low} hi={boot.ci_high} margin={comp.margin ?? 0.05} />}
          {boot && <p className="num mono text-[12px] text-muted">Δ {pts(boot.delta)} · 95% CI [{pts(boot.ci_low)}, {pts(boot.ci_high)}] · {boot.n_common_cases} matched cases · {boot.n_improved} better / {boot.n_regressed} worse</p>}
        </div>
      </div>
      <Ledger rows={rows} />
    </section>
  );
}

export default async function OverviewPage() {
  let o: Overview;
  let split: ReturnType<typeof splitKinds>;
  let live: ComparisonDetail | null = null;
  try {
    const [ov, runs, comps] = await Promise.all([api.overview(), api.runs({ page_size: 100 }), api.comparisons()]);
    o = ov; split = splitKinds(runs.items);
    const liveIds = comps.filter((c) => comparisonKind(c, runs.items) === "live").map((c) => c.id);
    const details = await Promise.all(liveIds.map((id) => api.comparison(id)));
    // the latest VALID live comparison is the answer to the product question; invalid ones live on the Experiments page
    live = details.filter((d) => d.valid && d.result).sort((a, b) => b.id - a.id)[0] ?? null;
  } catch (e) { return <ErrorState error={e} />; }
  if (o.empty) return <Card><EmptyState title="No data yet">Run <code>ars demo seed</code> to load the synthetic demo.</EmptyState></Card>;
  const { candidate: c, baseline: b } = o.kpis;
  const h = o.headline;
  const gatePass = o.gate?.verdict === "pass";
  return (
    <div className="space-y-6">
      <h1 className="max-w-[40ch] text-[22px] font-semibold leading-tight tracking-tight sm:text-[26px]">Did the latest change improve reliability, cause a regression, or leave us without enough evidence?</h1>
      {live && <LiveVerdict comp={live} />}

      <section aria-labelledby="synthetic" className="space-y-4 pt-2">
        <div className="flex flex-wrap items-baseline justify-between gap-2 border-t border-line pt-5">
          <h2 id="synthetic" className="text-[15px] font-semibold tracking-tight">Synthetic demonstration <span className="ml-1 align-middle"><KindBadge kind="synthetic" /></span></h2>
          <p className="max-w-xl text-[12.5px] text-muted">Scripted agents with injected faults. These numbers show how the instrument behaves; they say nothing about any real model.</p>
        </div>
      <Card aria-labelledby="headline">
        <div className="grid gap-5 p-4 lg:grid-cols-[1.1fr_1fr]">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[11px] font-medium text-faint">Baseline</span>
              <Badge>{h.baseline_label}</Badge><span aria-hidden className="text-faint">→</span>
              <span className="text-[11px] font-medium text-faint">Candidate</span>
              <Badge tone="info">{h.candidate_label}</Badge>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <DecisionBadge decision={h.decision} />
              <Badge tone={gatePass ? "ok" : "bad"} title={o.gate?.reasons.join("; ")}>CI gate: {gatePass ? "PASS" : "FAIL"}</Badge>
              <Badge title="Statistical policy used for this comparison">policy {h.policy_name}</Badge>
            </div>
            <p id="headline" className="text-[15px] leading-relaxed">{h.explanation}</p>
            {o.what_changed && (
              <div className="rounded-md border border-line bg-panel2 px-3 py-2.5">
                <div className="text-[12px] font-medium text-muted">What changed?</div>
                <p className="mt-1 text-sm">{o.what_changed}</p>
              </div>
            )}
            <Link href={`/compare/${h.id}`} className="inline-block text-sm font-medium text-accent hover:underline">Open full comparison →</Link>
          </div>
          <div>
            <div className="mb-1 text-[11px] font-medium text-faint">Pass-rate change, candidate − baseline (points)</div>
            {h.delta !== null && h.ci_low !== null && h.ci_high !== null && h.margin !== null && <CiPlot delta={h.delta} lo={h.ci_low} hi={h.ci_high} margin={h.margin} />}
            <p className="num mt-1 text-xs text-muted">
              Δ {pts(h.delta)} · 95% CI [{pts(h.ci_low, 1)}, {pts(h.ci_high, 1)}] · margin −{((h.margin ?? 0) * 100).toFixed(0)} pts · {h.n_common_cases} matched cases · bootstrap resamples cases, not samples
            </p>
          </div>
        </div>
      </Card>

      <section aria-label="Key metrics" className="space-y-2">
        <h3 className="text-[13px] font-medium">Candidate metrics <span className="font-normal text-muted">{o.candidate.agent} {o.candidate.agent_version} · {c.n_cases} cases × {o.candidate.samples_per_case} samples</span></h3>
        <Ledger rows={ledgerRows(c, b)} />
        <p className="text-[12px] text-faint">Evidence: {num(split.synthetic.samples)} synthetic samples in {split.synthetic.runs} runs. Live evidence is counted separately ({num(split.live.samples)} samples, {split.live.runs} runs) and never added to these.</p>
      </section>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card aria-labelledby="trend">
          <CardHeader id="trend" title="Task success by agent version" sub="Bars: pass rate. Whiskers: Wilson 95% CI. Support, research, coding and red-team suites." />
          <div className="p-3"><TrendChart points={o.trend} /></div>
        </Card>
        <Card aria-labelledby="fail">
          <CardHeader id="fail" title="What is breaking? Failure modes (candidate vs baseline)" sub="Colour = severity. Grey = baseline count." right={<Link className="text-xs text-accent hover:underline" href="/failures">Failure analysis →</Link>} />
          <div className="p-3">{o.failure_categories.length ? <FailureBars clusters={o.failure_categories} baseline={o.baseline_failure_categories} /> : <EmptyState title="No failures recorded" />}</div>
        </Card>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1fr_1.2fr]">
        <Card aria-labelledby="cat">
          <CardHeader id="cat" title="Change by category" sub="Candidate − baseline pass rate. Red bars are localized regressions inside an overall improvement." />
          <div className="p-3"><CategoryDeltaBars deltas={o.category_deltas} /></div>
        </Card>
        <Card aria-labelledby="recent">
          <CardHeader id="recent" title="Recent experiments" right={<Link className="text-xs text-accent hover:underline" href="/experiments">All experiments →</Link>} />
          <ul className="divide-y divide-line">
            {o.recent_runs.map((r) => (
              <li key={r.id} className="flex items-center justify-between gap-3 px-4 py-2.5">
                <div className="min-w-0">
                  <Link href={`/experiments/${r.id}`} className="block truncate font-medium text-accent hover:underline">{r.name}</Link>
                  <div className="text-xs text-muted">{r.agent} {r.agent_version} · {r.dataset}:{r.dataset_version} · {r.samples_per_case}×</div>
                </div>
                <div className="num shrink-0 text-right"><div className="font-medium">{pct(r.pass_rate)}</div><div className="text-[11px] text-faint">n={r.n_samples}</div></div>
              </li>
            ))}
          </ul>
        </Card>
      </div>
      </section>
    </div>
  );
}

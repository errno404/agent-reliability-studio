import Link from "next/link";
import { CategoryDeltaBars, CiPlot, FailureBars, TrendChart } from "@/components/charts";
import { Badge, Card, CardHeader, DecisionBadge, Delta, EmptyState, ErrorState, KindBadge, PageHeader, Stat, SyntheticBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { ms, num, pct, pts, usd } from "@/lib/format";
import { splitKinds } from "@/lib/live";
import type { Overview, Rate } from "@/lib/types";

export const dynamic = "force-dynamic";

function Kpi({ label, r, base }: { label: string; r: Rate; base?: Rate }) {
  const d = r.rate !== null && base?.rate !== null && base?.rate !== undefined ? r.rate - base.rate : null;
  return <Stat label={label} value={pct(r.rate)} n={r.n} ciLo={r.ci_low} ciHi={r.ci_high} sub={d !== null ? <>vs baseline <Delta v={d} /> pts</> : undefined} />;
}

export default async function OverviewPage() {
  let o: Overview;
  let split: ReturnType<typeof splitKinds>;
  try { [o, split] = await Promise.all([api.overview(), api.runs({ page_size: 100 }).then((r) => splitKinds(r.items))]); } catch (e) { return <ErrorState error={e} />; }
  if (o.empty) return <Card><EmptyState title="No data yet">Run <code>ars demo seed</code> to load the synthetic demo.</EmptyState></Card>;
  const { candidate: c, baseline: b } = o.kpis;
  const h = o.headline;
  const gatePass = o.gate?.verdict === "pass";
  return (
    <div className="space-y-5">
      <PageHeader
        title="Did this agent change improve reliability?"
        sub="Evidence, not vibes: deterministic checks, trajectory analysis, repeated trials and a statistical gate. Below: the current baseline → candidate comparison."
        right={<span className="flex items-center gap-2"><KindBadge kind="synthetic" /><SyntheticBadge /></span>}
      />
      {split.live.runs > 0 && <p className="text-[13px] text-muted">Everything on this page is <b>synthetic</b> (scripted agents). Real-model evidence is separate: <Link className="text-accent hover:underline" href="/experiments">Experiment 001 — live runs →</Link></p>}

      <Card aria-labelledby="headline">
        <div className="grid gap-5 p-4 lg:grid-cols-[1.1fr_1fr]">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[11px] font-medium uppercase tracking-wider text-faint">Baseline</span>
              <Badge>{h.baseline_label}</Badge><span aria-hidden className="text-faint">→</span>
              <span className="text-[11px] font-medium uppercase tracking-wider text-faint">Candidate</span>
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
                <div className="text-[11px] font-semibold uppercase tracking-wider text-faint">What changed?</div>
                <p className="mt-1 text-sm">{o.what_changed}</p>
              </div>
            )}
            <Link href={`/compare/${h.id}`} className="inline-block text-sm font-medium text-accent hover:underline">Open full comparison →</Link>
          </div>
          <div>
            <div className="mb-1 text-[11px] font-medium uppercase tracking-wider text-faint">Pass-rate change, candidate − baseline (points)</div>
            {h.delta !== null && h.ci_low !== null && h.ci_high !== null && h.margin !== null && <CiPlot delta={h.delta} lo={h.ci_low} hi={h.ci_high} margin={h.margin} />}
            <p className="num mt-1 text-xs text-muted">
              Δ {pts(h.delta)} · 95% CI [{pts(h.ci_low, 1)}, {pts(h.ci_high, 1)}] · margin −{((h.margin ?? 0) * 100).toFixed(0)} pts · {h.n_common_cases} matched cases · bootstrap resamples cases, not samples
            </p>
          </div>
        </div>
      </Card>

      <section aria-label="Key metrics" className="space-y-2">
        <div className="flex items-baseline justify-between">
          <h2 className="text-[13px] font-semibold">Candidate metrics <span className="font-normal text-muted">({o.candidate.agent} {o.candidate.agent_version}, {c.n_cases} cases × {o.candidate.samples_per_case} samples)</span></h2>
        </div>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Kpi label="Task success" r={c.task_success} base={b.task_success} />
          <Kpi label="Outcome pass" r={c.outcome} base={b.outcome} />
          <Kpi label="Trajectory pass" r={c.trajectory} base={b.trajectory} />
          <Kpi label="Tool / component pass" r={c.component} base={b.component} />
          <Kpi label="Policy / safety pass" r={c.policy} base={b.policy} />
          <Stat label="pass^k (reliability)" value={pct(c.pass_hat_k, 0)} sub={<>k={c.k} · baseline {pct(b.pass_hat_k, 0)}</>} hint="Fraction of tasks that pass EVERY repetition" />
          <Stat label="pass@k (capability)" value={pct(c.pass_at_k, 0)} sub={<>k={c.k} · baseline {pct(b.pass_at_k, 0)}</>} hint="Fraction of tasks that pass AT LEAST ONCE" />
          <Stat label="Execution errors" value={pct(c.execution_error_rate)} sub="excluded from quality" tone={c.execution_error_rate > 0.05 ? "warn" : undefined} n={c.n_samples} />
          <Stat label="Latency p50 / p95" value={<>{ms(c.latency_p50_ms)}<span className="text-base text-muted"> / {ms(c.latency_p95_ms)}</span></>} sub="virtual clock (synthetic)" />
          <Stat label="Total tokens" value={num(c.total_tokens)} sub={`in ${num(c.input_tokens)} · out ${num(c.output_tokens)}`} />
          <Stat label="API-equivalent cost" value={usd(c.cost_usd)} sub={c.cost_usd === null ? "pricing unavailable" : "synthetic price table"} hint="Estimated from a versioned price table; not money spent." />
          <Stat label="Evidence (synthetic)" value={num(split.synthetic.samples)} sub={`${split.synthetic.runs} synthetic runs · live evidence is separate: ${num(split.live.samples)} samples in ${split.live.runs} runs`} hint="Synthetic and live runs are never added together" />
        </div>
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
    </div>
  );
}

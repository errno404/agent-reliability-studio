import Link from "next/link";
import { CategoryDeltaBars, CiPlot } from "@/components/charts";
import { Trajectory } from "@/components/samples-table";
import { Badge, Card, CardHeader, Crumbs, DecisionBadge, Delta, ErrorState, HashChip, PageHeader, SyntheticBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { label, ms, num, pct, pts, usd } from "@/lib/format";
import type { ComparisonResult, Summary, Validity } from "@/lib/types";

export const dynamic = "force-dynamic";

function Row({ name, b, c, fmt, d, invert, note }: { name: string; b: number | null; c: number | null; fmt: (v: number) => string; d?: number | null; invert?: boolean; note?: string }) {
  const delta = d !== undefined ? d : b !== null && c !== null ? c - b : null;
  return (
    <tr>
      <th scope="row" className="px-3 py-2 text-left font-medium">{name}{note && <div className="text-[11px] font-normal text-faint">{note}</div>}</th>
      <td className="num px-3 py-2">{b === null ? "—" : fmt(b)}</td><td className="num px-3 py-2">{c === null ? "—" : fmt(c)}</td>
      <td className="num px-3 py-2"><Delta v={delta} invert={invert} /></td>
    </tr>
  );
}

export default async function ComparePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  try {
    const comp = await api.comparison(Number(id));
    const r = comp.result as unknown as ComparisonResult;
    const v = comp.validity as unknown as Validity;
    const boot = r.bootstrap;
    const bs = r.baseline_summary as Summary | undefined;
    const cs = r.candidate_summary as Summary | undefined;
    const rate = (x?: { rate: number | null }) => x?.rate ?? null;
    return (
      <>
        <Crumbs items={[{ href: "/compare", label: "Compare" }, { label: comp.name }]} />
        <PageHeader title={comp.name} sub={<span className="flex flex-wrap items-center gap-2"><Badge>{comp.baseline_label}</Badge>→<Badge tone="info">{comp.candidate_label}</Badge><span>mode {comp.mode}</span><span>policy {comp.policy_name}</span></span>} right={<SyntheticBadge />} />

        <Card>
          <div className="space-y-3 p-4">
            <div className="flex flex-wrap items-center gap-2"><DecisionBadge decision={comp.decision} />{comp.gate_verdict && <Badge tone={comp.gate_verdict === "pass" ? "ok" : "bad"}>CI gate: {comp.gate_verdict.toUpperCase()}</Badge>}</div>
            <p className="text-[15px]">{comp.explanation}</p>
            {r.what_changed && <p className="rounded-md bg-panel2 px-3 py-2 text-sm"><b>What changed: </b>{r.what_changed}</p>}
          </div>
          {boot && (
            <div className="grid gap-4 border-t border-line p-4 lg:grid-cols-[1fr_1fr]">
              <div><CiPlot delta={boot.delta} lo={boot.ci_low} hi={boot.ci_high} margin={comp.margin ?? 0.05} /></div>
              <dl className="num grid grid-cols-2 gap-x-4 gap-y-1.5 self-center text-[13px]">
                <dt className="text-muted">Overall Δ</dt><dd className="font-medium">{pts(boot.delta)}</dd>
                <dt className="text-muted">95% CI</dt><dd>[{pts(boot.ci_low)}, {pts(boot.ci_high)}]</dd>
                <dt className="text-muted">Regression margin</dt><dd>−{((comp.margin ?? 0) * 100).toFixed(0)} pts</dd>
                <dt className="text-muted">Matched cases</dt><dd>{boot.n_common_cases} (min {String((comp.policy as { min_cases?: number }).min_cases)})</dd>
                <dt className="text-muted">Samples / case</dt><dd>{comp.baseline.samples_per_case} · {comp.candidate.samples_per_case}</dd>
                <dt className="text-muted">Improved / regressed / same</dt><dd>{boot.n_improved} / {boot.n_regressed} / {boot.n_unchanged}</dd>
                <dt className="text-muted">Bootstrap</dt><dd>{String((comp.policy as { n_boot?: number }).n_boot)} case-level resamples</dd>
                {r.mcnemar && <><dt className="text-muted">McNemar (diagnostic)</dt><dd title={r.mcnemar.note}>b={r.mcnemar.b}, c={r.mcnemar.c}, p={r.mcnemar.p_value.toFixed(3)}</dd></>}
              </dl>
            </div>
          )}
          {(v.reasons.length > 0 || v.warnings.length > 0) && (
            <div className="space-y-2 border-t border-line p-4">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-faint">Validity</div>
              {v.reasons.map((x) => <div key={x} className="rounded border border-info/30 bg-info-soft px-3 py-2 text-sm"><b>Blocking:</b> <span className="font-mono text-xs">{x}</span></div>)}
              {v.warnings.map((x) => <div key={x} className="rounded border border-warn/30 bg-warn-soft px-3 py-2 text-sm"><b>Warning:</b> <span className="font-mono text-xs">{x}</span></div>)}
            </div>
          )}
        </Card>

        {bs && cs && (
          <div className="mt-5 grid gap-5 lg:grid-cols-[1.2fr_1fr]">
            <Card><CardHeader title="Metric comparison" sub="Separate scoring layers; never blended into one score." />
              <div className="scroll-x"><table className="w-full min-w-[460px] text-[13px]">
                <thead className="border-b border-line text-[11px] uppercase tracking-wider text-faint"><tr><th className="px-3 py-2 text-left font-medium">Metric</th><th className="px-3 py-2 text-left font-medium">Baseline</th><th className="px-3 py-2 text-left font-medium">Candidate</th><th className="px-3 py-2 text-left font-medium">Δ (pts)</th></tr></thead>
                <tbody className="divide-y divide-line">
                  <Row name="Task success" b={rate(bs.task_success)} c={rate(cs.task_success)} fmt={pct} note={`n=${bs.task_success.n} vs ${cs.task_success.n}`} />
                  <Row name="Outcome" b={rate(bs.outcome)} c={rate(cs.outcome)} fmt={pct} />
                  <Row name="Trajectory" b={rate(bs.trajectory)} c={rate(cs.trajectory)} fmt={pct} />
                  <Row name="Components / tools" b={rate(bs.component)} c={rate(cs.component)} fmt={pct} />
                  <Row name="Policy / safety" b={rate(bs.policy)} c={rate(cs.policy)} fmt={pct} />
                  <Row name="pass^k (reliability)" b={bs.pass_hat_k} c={cs.pass_hat_k} fmt={(x) => pct(x, 0)} />
                  <Row name="pass@k (capability)" b={bs.pass_at_k} c={cs.pass_at_k} fmt={(x) => pct(x, 0)} />
                  <Row name="Latency p50" b={bs.latency_p50_ms} c={cs.latency_p50_ms} fmt={ms} d={cs.latency_p50_ms / (bs.latency_p50_ms || 1) - 1} invert note="Δ as relative change" />
                  <Row name="Latency p95" b={bs.latency_p95_ms} c={cs.latency_p95_ms} fmt={ms} d={cs.latency_p95_ms / (bs.latency_p95_ms || 1) - 1} invert note="Δ as relative change" />
                  <Row name="Tokens" b={bs.total_tokens} c={cs.total_tokens} fmt={num} d={cs.total_tokens / (bs.total_tokens || 1) - 1} invert note="Δ as relative change" />
                  <Row name="API-equivalent cost" b={bs.cost_usd} c={cs.cost_usd} fmt={usd} d={bs.cost_usd && cs.cost_usd ? cs.cost_usd / bs.cost_usd - 1 : null} invert note="synthetic price table; not money spent" />
                </tbody></table></div>
            </Card>
            <Card><CardHeader title="Category deltas" sub="Where the change landed." /><div className="p-3"><CategoryDeltaBars deltas={r.category_deltas} /></div></Card>
          </div>
        )}

        <Card className="mt-5">
          <CardHeader title={`Changed cases (${r.case_changes.length})`} sub="Click a case for the side-by-side trajectory, arguments, assertions and traces." />
          {r.case_changes.length === 0 ? <p className="px-4 py-8 text-center text-sm text-muted">{comp.valid ? "No case changed." : "Case drill-down is unavailable for an invalid comparison."}</p> : (
            <div className="scroll-x"><table className="w-full min-w-[700px] text-[13px]"><thead className="border-b border-line text-[11px] uppercase tracking-wider text-faint"><tr>{["Case", "Category", "Result", "Baseline", "Candidate", "Trajectory change"].map((h) => <th key={h} className="px-3 py-2 text-left font-medium">{h}</th>)}</tr></thead>
              <tbody className="divide-y divide-line">
                {[...r.case_changes].sort((a, b) => a.delta - b.delta).map((c) => (
                  <tr key={c.case_id} className="hover:bg-panel2">
                    <td className="px-3 py-2"><Link className="font-medium text-accent hover:underline" href={`/compare/${comp.id}/cases/${c.case_id}`}>{c.case_id}</Link></td>
                    <td className="px-3 py-2 text-muted">{label(c.category)}</td>
                    <td className="px-3 py-2"><Badge tone={c.kind === "regressed" ? "bad" : "ok"}>{c.kind}</Badge></td>
                    <td className="num px-3 py-2">{pct(c.baseline, 0)}</td><td className="num px-3 py-2">{pct(c.candidate, 0)}</td>
                    <td className="px-3 py-2">{c.trajectory_diff && !c.trajectory_diff.identical ? <Trajectory tools={c.trajectory_diff.candidate} max={4} /> : <span className="text-faint">same tools</span>}</td>
                  </tr>))}
              </tbody></table></div>
          )}
        </Card>

        <Card className="mt-5"><CardHeader title="Runs compared" />
          <div className="grid gap-4 p-4 sm:grid-cols-2 text-[13px]">
            {[comp.baseline, comp.candidate].map((run, i) => (
              <div key={run.id} className="space-y-1"><div className="text-[11px] font-semibold uppercase tracking-wider text-faint">{i ? "Candidate" : "Baseline"}</div>
                <Link className="font-medium text-accent hover:underline" href={`/experiments/${run.id}`}>{run.name}</Link>
                <div className="flex flex-wrap gap-1.5"><HashChip label="dataset" value={run.dataset_hash} /><Badge>{run.samples_per_case}× samples</Badge><Badge>{run.n_cases} cases</Badge><Badge>{run.status}</Badge></div>
              </div>))}
          </div>
        </Card>
      </>
    );
  } catch (e) { return <ErrorState error={e} />; }
}

import Link from "next/link";
import { CategoryDeltaBars, CiPlot } from "@/components/charts";
import { Trajectory } from "@/components/samples-table";
import { Badge, Card, CardHeader, Crumbs, DecisionBadge, Delta, ErrorState, HashChip, KindBadge, LiveNote, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { label, ms, num, pct, pts, usd } from "@/lib/format";
import { comparisonKind, controlledVariables, intentLabel, modeLabel } from "@/lib/live";
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
    const [bRun, cRun] = await Promise.all([api.run(comp.baseline.id), api.run(comp.candidate.id)]);
    const r = comp.result as unknown as ComparisonResult;
    const v = comp.validity as unknown as Validity;
    const boot = r.bootstrap;
    const bs = r.baseline_summary as Summary | undefined;
    const cs = r.candidate_summary as Summary | undefined;
    const rate = (x?: { rate: number | null }) => x?.rate ?? null;
    const kind = comparisonKind({ baseline_run_id: comp.baseline.id, candidate_run_id: comp.candidate.id }, [comp.baseline, comp.candidate]);
    const mode = comp.valid ? modeLabel(comp.mode, r.authorization) : { text: `${comp.mode.toUpperCase()} · INVALID — cannot authorise a release`, tone: "warn" as const };
    const cv = controlledVariables(comp.intent);
    const mb = bRun.manifest as Record<string, string>, mc = cRun.manifest as Record<string, string>;
    const e2e = r.end_to_end, cov = r.coverage;
    return (
      <>
        <Crumbs items={[{ href: "/compare", label: "Compare" }, { label: comp.name }]} />
        <PageHeader title={comp.name} sub={<span className="flex flex-wrap items-center gap-2"><Badge>{comp.baseline_label}</Badge>→<Badge tone="info">{comp.candidate_label}</Badge><span>policy {comp.policy_name}</span><Badge tone={mode.tone} title="Strict mode is the only mode that can authorise a release; research / exploratory comparisons are diagnostic.">{mode.text}</Badge><Badge title="What the author declared changed. Everything else is a controlled variable and must match.">intent: {intentLabel(comp.intent)}</Badge></span>} right={<KindBadge kind={kind} />} />
        {kind === "live" && <div className="mb-4"><LiveNote /></div>}

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

        <Card className="mt-5" aria-labelledby="prov">
          <CardHeader id="prov" title="Provenance and controlled variables" sub={`Declared intent: ${intentLabel(comp.intent)}. A comparison is only fair if everything that is not the declared change matches.`} />
          <div className="grid gap-4 p-4 lg:grid-cols-2">
            <div className="space-y-2 text-[13px]">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-faint">May differ (declared by intent)</div>
              <div className="flex flex-wrap gap-1.5">{cv.varied.length ? cv.varied.map((x) => <Badge key={x} tone="info">{x}</Badge>) : <span className="text-muted">nothing but the agent / prompt itself</span>}</div>
              <div className="text-[11px] font-semibold uppercase tracking-wider text-faint">Must match (controlled)</div>
              <div className="flex flex-wrap gap-1.5">{cv.controlled.map((x) => <Badge key={x}>{x}</Badge>)}</div>
            </div>
            <dl className="grid grid-cols-[140px_1fr] gap-x-3 gap-y-1.5 self-start text-[13px]">
              <dt className="text-muted">Kind</dt><dd className="font-mono text-xs">{comp.baseline.execution_kind} → {comp.candidate.execution_kind}</dd>
              <dt className="text-muted">Agent hash</dt><dd><HashChip value={bRun.agent_hash} /> → <HashChip value={cRun.agent_hash} /></dd>
              <dt className="text-muted">Model</dt><dd className="font-mono text-xs">{mb.model_resolved || comp.baseline.model} → {mc.model_resolved || comp.candidate.model}</dd>
              <dt className="text-muted">Evaluator code</dt><dd><HashChip value={String(mb.evaluator_hash ?? "")} /> → <HashChip value={String(mc.evaluator_hash ?? "")} /></dd>
              <dt className="text-muted">Dataset</dt><dd><HashChip value={comp.baseline.dataset_hash} /> → <HashChip value={comp.candidate.dataset_hash} /></dd>
              <dt className="text-muted">Fixture</dt><dd><HashChip value={String(mb.fixture_hash ?? "")} /> → <HashChip value={String(mc.fixture_hash ?? "")} /></dd>
            </dl>
          </div>
          {!comp.valid && <p className="border-t border-line px-4 py-3 text-[13px] text-muted"><b className="text-fg">Why this is INVALID, not &ldquo;close enough&rdquo;:</b> one or more controlled variables differ (see the blocking reasons above). No statistic is computed, and nothing here can authorise a release. {v.reasons.some((x) => x.startsWith("evaluator_changed")) ? "The evaluator code hash differs between the two runs, so a different measuring instrument produced each side; re-run both sides under one evaluator version." : ""}</p>}
        </Card>

        {cov && (
          <Card className="mt-5" aria-labelledby="cov">
            <CardHeader id="cov" title="Evidence coverage and sensitivity" sub="Missing or errored observations are never silently dropped." />
            <div className="scroll-x"><table className="w-full min-w-[480px] text-[13px]"><thead className="border-b border-line text-[11px] uppercase tracking-wider text-faint"><tr>{["Run", "Expected", "Present", "Missing", "Exec. errors", "Invalid", "Incomplete share"].map((h) => <th key={h} className="px-3 py-2 text-left font-medium">{h}</th>)}</tr></thead>
              <tbody className="divide-y divide-line">{(["baseline", "candidate"] as const).map((k) => <tr key={k}><th scope="row" className="px-3 py-2 text-left font-medium capitalize">{k}</th>{[cov[k].expected, cov[k].present, cov[k].missing, cov[k].execution_error, cov[k].invalid].map((x, i) => <td key={i} className="num px-3 py-2">{x}</td>)}<td className="num px-3 py-2">{pct(cov[k].incomplete_share)}</td></tr>)}</tbody></table></div>
            {e2e && <p className="num border-t border-line px-4 py-3 text-[13px]"><b>End-to-end sensitivity</b> (unusable observations counted as failures): Δ {pts(e2e.delta)} · 95% CI [{pts(e2e.ci_low)}, {pts(e2e.ci_high)}] over {e2e.n_cases} cases → <DecisionBadge decision={e2e.decision} /> <span className="text-muted">{e2e.note}</span></p>}
            {(r.incomplete_reasons ?? []).length > 0 && <ul className="border-t border-line px-4 py-3 text-sm text-warn">{(r.incomplete_reasons ?? []).map((x) => <li key={x}>{x}</li>)}</ul>}
          </Card>
        )}

        {bs && cs && (
          <div className="mt-5 grid gap-5 lg:grid-cols-[1.2fr_1fr]">
            <Card><CardHeader title="Metric comparison" sub={comp.valid ? "Separate scoring layers; never blended into one score." : "Descriptive only: this comparison is invalid, so no difference below is a result and none can authorise anything."} />
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

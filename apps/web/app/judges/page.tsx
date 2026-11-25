import Link from "next/link";
import { Badge, Card, ErrorState, HashChip, PageHeader, SyntheticBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { pct, shortDate } from "@/lib/format";
import { releaseScope, scopeLabel } from "@/lib/live";
import type { CalRun, JudgeOut } from "@/lib/types";

export const metadata = { title: "Judges" };
export const dynamic = "force-dynamic";

function Confusion({ m }: { m: CalRun["metrics"] }) {
  const cell = (v: number, bad: boolean) => <td className={`num h-14 w-28 border border-line text-center text-lg font-semibold ${bad && v > 0 ? "bg-bad-soft text-bad" : "bg-panel2"}`}>{v}</td>;
  return (
    <table className="text-xs" aria-label="Confusion matrix: rows are reference labels, columns are judge verdicts">
      <thead><tr><th /><th scope="col" className="px-2 pb-1 font-medium text-faint">judge: pass</th><th scope="col" className="px-2 pb-1 font-medium text-faint">judge: fail</th></tr></thead>
      <tbody><tr><th scope="row" className="pr-2 text-right font-medium text-faint">reference: pass</th>{cell(m.tp, false)}{cell(m.fn, true)}</tr>
        <tr><th scope="row" className="pr-2 text-right font-medium text-faint">reference: fail</th>{cell(m.fp, true)}{cell(m.tn, false)}</tr></tbody>
    </table>
  );
}

function JudgeCard({ j, errors }: { j: JudgeOut; errors: { item_id: string; candidate_output: string; reference_label: boolean; predicted: boolean; notes: string }[] }) {
  const latest = j.latest as unknown as CalRun | null;
  const history = j.history as unknown as CalRun[];
  const m = latest?.metrics;
  const rel = releaseScope(latest);
  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
        <div className="flex items-center gap-2 text-[14px] font-medium" role="status"><span aria-hidden className={`size-2 rounded-full ${j.admitted && rel.eligible ? "bg-ok" : j.admitted ? "bg-warn" : "bg-bad"}`} />{j.status_label}</div>
        <div className="flex flex-wrap items-center gap-2 text-xs"><Badge>{j.backend}</Badge><span className="font-mono font-medium">{j.model}</span><HashChip label="prompt" value={j.prompt_hash} /><Badge>{j.dimension}</Badge><Badge>rubric {j.rubric_version}</Badge><HashChip label="identity" value={j.identity} /></div>
      </div>
      {!latest || !m ? (
        <p className="p-4 text-sm text-muted">This exact configuration (backend + model + prompt hash) has <b>never been calibrated</b>. Changing any of the three requires a new calibration, so this judge is diagnostic-only and cannot gate a release.</p>
      ) : (
        <div className="space-y-4 p-4">
          <dl className="num grid grid-cols-2 gap-x-6 gap-y-2 text-[13px] sm:grid-cols-4 lg:grid-cols-7">
            {([["Items", String(m.n), `${m.n_pos} pass · ${m.n_neg} fail`, ""], ["Accuracy", pct(m.accuracy), "", ""], ["Precision", pct(m.precision), "", ""], ["Recall", pct(m.recall), "", ""], ["F1", m.f1.toFixed(2), "", ""],
              ["Cohen's κ", m.kappa.toFixed(2), `need ≥ ${latest.policy.min_kappa}`, m.kappa >= Number(latest.policy.min_kappa) ? "text-ok" : "text-bad"],
              ["False-positive rate", pct(m.fpr), `need ≤ ${pct(Number(latest.policy.max_fpr), 0)} · upper ${rel.fprUpper === null ? "—" : pct(rel.fprUpper)}`, m.fpr <= Number(latest.policy.max_fpr) ? "text-ok" : "text-bad"]] as const).map(([k, v, sub, tone]) => (
              <div key={k}><dt className="text-[12px] text-muted">{k}</dt><dd className={`mono text-[17px] font-medium ${tone}`}>{v}</dd>{sub && <div className="text-[11px] text-faint">{sub}</div>}</div>))}
          </dl>
          <div role="status" aria-label="Release eligibility" className={`border-l-2 px-3 py-2.5 text-[13px] ${rel.eligible ? "border-ok" : "border-warn"}`}>
            <div className="flex flex-wrap items-center gap-2"><Badge tone={rel.eligible ? "ok" : "warn"}>{scopeLabel(rel.scope)}</Badge>
              <span className="num">95% Wilson upper bound on FPR: <b>{rel.fprUpper === null ? "—" : pct(rel.fprUpper)}</b> <span className="text-muted">(point {pct(m.fpr)} from {m.fp} of {rel.nNegatives} negatives)</span></span></div>
            {rel.reasons.length > 0 && <ul className="mt-1.5 list-inside list-disc text-muted">{rel.reasons.map((x) => <li key={x}>{x}</li>)}</ul>}
            {rel.scope === "demonstration" && <p className="mt-1.5 text-xs text-muted">Synthetic fixture labels can demonstrate the calibration workflow but never authorise a release; a release needs ≥ {String(latest.policy.min_trusted_items ?? 50)} human/adjudicated labels and a FPR upper bound ≤ {pct(Number(latest.policy.max_fpr_upper ?? 0.1), 0)}.</p>}
          </div>
          <div className="grid gap-5 lg:grid-cols-[auto_1fr]">
            <div><div className="mb-1 text-[12px] font-medium text-muted">Confusion matrix</div><Confusion m={m} /></div>
            <div className="space-y-2 text-[13px]">
              <div className="text-[12px] font-medium text-muted">Admission policy ({String(latest.policy.version)}) — stored with this calibration</div>
              <p className="text-muted">≥ {String(latest.policy.min_items)} labelled items · ≥ {String(latest.policy.min_per_class)} per class · κ ≥ {String(latest.policy.min_kappa)} · FPR ≤ {pct(Number(latest.policy.max_fpr), 0)}. These are starting defaults, not universal truths.</p>
              {latest.reasons.length > 0 && <ul className="list-inside list-disc text-bad">{latest.reasons.map((r) => <li key={r}>{r}</li>)}</ul>}
              <p className="text-xs text-muted">Reference labels: {Object.entries(latest.reference_sources).map(([k, v]) => `${v} ${k}`).join(", ")} — <b>synthetic fixture labels, not human labels</b>.</p>
            </div>
          </div>
          {errors.length > 0 && (
            <details className="rounded border border-line"><summary className="cursor-pointer px-3 py-2 text-[13px] font-medium">Where the judge disagreed with the reference ({errors.length})</summary>
              <ul className="divide-y divide-line">{errors.slice(0, 12).map((e) => (
                <li key={e.item_id} className="space-y-0.5 px-3 py-2 text-[13px]"><div className="flex items-center gap-2"><span className="font-mono text-xs">{e.item_id}</span><Badge tone={e.reference_label ? "ok" : "bad"}>ref: {e.reference_label ? "pass" : "fail"}</Badge><Badge tone={e.predicted ? "ok" : "bad"}>judge: {e.predicted ? "pass" : "fail"}</Badge></div><p className="text-muted">{e.candidate_output}</p>{e.notes && <p className="text-xs text-faint">{e.notes}</p>}</li>))}</ul></details>)}
          {history.length > 1 && <div><div className="mb-1 text-[12px] font-medium text-muted">Calibration history</div>
            <ul className="space-y-1 text-[13px]">{history.map((h) => <li key={h.id} className="flex flex-wrap items-center gap-2"><Badge tone={h.admitted ? "ok" : "bad"}>{h.admitted ? "admitted" : "not admitted"}</Badge><span className="num">n={h.n_items_used}</span><span className="num text-muted">κ {h.metrics.kappa.toFixed(2)} · FPR {pct(h.metrics.fpr)}</span><span className="text-faint">{shortDate(h.created_at)}</span>{h.reasons[0] && <span className="text-xs text-muted">— {h.reasons[0]}</span>}</li>)}</ul></div>}
        </div>
      )}
    </Card>
  );
}

/** One row per judge identity: can it gate a release, or is it diagnostic? The question this page exists to answer. */
function Registry({ judges }: { judges: JudgeOut[] }) {
  return (
    <section aria-labelledby="registry" className="space-y-2">
      <h2 id="registry" className="text-[15px] font-semibold tracking-tight">Which judges can gate a release?</h2>
      <p className="max-w-[70ch] text-[13px] text-muted">A judge is identified by backend, model, prompt, rubric and configuration. Calibration on synthetic labels shows the workflow but never authorises a release; that needs enough human or adjudicated labels and a low false-positive upper bound. Right now no judge qualifies.</p>
      <div className="scroll-x"><table className="w-full min-w-[720px] text-[13px]">
        <thead><tr className="border-b border-line-strong text-left text-[12px] text-muted"><th className="py-1.5 pr-3 font-medium">Judge</th><th className="px-3 py-1.5 font-medium">Scope</th><th className="px-3 py-1.5 text-right font-medium">κ</th><th className="px-3 py-1.5 text-right font-medium">FPR (upper 95%)</th><th className="px-3 py-1.5 text-right font-medium">Labels</th><th className="py-1.5 pl-3 font-medium">Identity</th></tr></thead>
        <tbody className="divide-y divide-line">{judges.map((j) => { const l = j.latest as unknown as CalRun | null; const r = releaseScope(l); return (
          <tr key={j.id}><th scope="row" className="py-1.5 pr-3 text-left font-normal"><span className="mono">{j.model}</span> <span className="text-faint">rubric {j.rubric_version}</span></th>
            <td className="px-3 py-1.5"><Badge tone={r.eligible ? "ok" : l ? "warn" : "bad"}>{l ? scopeLabel(r.scope) : "diagnostic only · never calibrated"}</Badge></td>
            <td className="num mono px-3 py-1.5 text-right">{l ? l.metrics.kappa.toFixed(2) : "—"}</td>
            <td className="num mono px-3 py-1.5 text-right">{r.fprUpper === null ? "—" : pct(r.fprUpper)}</td>
            <td className="num mono px-3 py-1.5 text-right">{l ? `${r.trusted} trusted / ${l.n_items_used}` : "—"}</td>
            <td className="mono py-1.5 pl-3 text-[12px] text-faint">{j.identity.slice(0, 8)}</td></tr>); })}</tbody></table></div>
    </section>
  );
}

export default async function JudgesPage() {
  try {
    const judges = await api.judges();
    const errs = await Promise.all(judges.map(async (j) => (j.latest ? (await api.calibrationItems((j.latest as unknown as CalRun).id)).items.filter((i) => i.predicted !== i.reference_label) : [])));
    return (
      <>
        <PageHeader title="Judge calibration" sub="An LLM judge is a model that must itself be evaluated. Only a judge whose exact configuration passed calibration may affect a release decision; everything else is diagnostic." right={<div className="flex items-center gap-2"><SyntheticBadge /><Link href="/judges/annotate" className="rounded-sm border border-line-strong px-3 py-1.5 text-sm font-medium hover:bg-panel2">Annotate items</Link></div>} />
        <Registry judges={judges} />
        <h2 className="mb-2 mt-8 text-[15px] font-semibold tracking-tight">Calibration detail</h2>
        <div className="space-y-5">{judges.map((j, i) => <JudgeCard key={j.id} j={j} errors={errs[i] as never} />)}</div>
      </>
    );
  } catch (e) { return <ErrorState error={e} />; }
}

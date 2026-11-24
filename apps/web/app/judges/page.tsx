import Link from "next/link";
import { Badge, Card, ErrorState, HashChip, PageHeader, Stat, SyntheticBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { pct, shortDate } from "@/lib/format";
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
  return (
    <Card>
      <div className={`flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3 ${j.admitted ? "border-ok/30 bg-ok-soft" : "border-bad/30 bg-bad-soft"}`}>
        <div className={`text-[15px] font-bold tracking-wide ${j.admitted ? "text-ok" : "text-bad"}`} role="status">{j.status_label}</div>
        <div className="flex flex-wrap items-center gap-2 text-xs"><Badge>{j.backend}</Badge><span className="font-mono font-medium">{j.model}</span><HashChip label="prompt" value={j.prompt_hash} /><Badge>{j.dimension}</Badge><Badge>rubric {j.rubric_version}</Badge><HashChip label="identity" value={j.identity} /></div>
      </div>
      {!latest || !m ? (
        <p className="p-4 text-sm text-muted">This exact configuration (backend + model + prompt hash) has <b>never been calibrated</b>. Changing any of the three requires a new calibration, so this judge is diagnostic-only and cannot gate a release.</p>
      ) : (
        <div className="space-y-4 p-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-7">
            <Stat label="Items" value={m.n} sub={`${m.n_pos} pass · ${m.n_neg} fail`} hint="Class balance of reference labels" />
            <Stat label="Accuracy" value={pct(m.accuracy)} /><Stat label="Precision" value={pct(m.precision)} /><Stat label="Recall" value={pct(m.recall)} /><Stat label="F1" value={m.f1.toFixed(2)} />
            <Stat label="Cohen's κ" value={m.kappa.toFixed(2)} tone={m.kappa >= Number(latest.policy.min_kappa) ? "ok" : "bad"} sub={`need ≥ ${latest.policy.min_kappa}`} />
            <Stat label="False-positive rate" value={pct(m.fpr)} tone={m.fpr <= Number(latest.policy.max_fpr) ? "ok" : "bad"} sub={`need ≤ ${pct(Number(latest.policy.max_fpr), 0)} · FNR ${pct(m.fnr)}`} />
          </div>
          <div className="grid gap-5 lg:grid-cols-[auto_1fr]">
            <div><div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-faint">Confusion matrix</div><Confusion m={m} /></div>
            <div className="space-y-2 text-[13px]">
              <div className="text-[11px] font-semibold uppercase tracking-wider text-faint">Admission policy ({String(latest.policy.version)}) — stored with this calibration</div>
              <p className="text-muted">≥ {String(latest.policy.min_items)} labelled items · ≥ {String(latest.policy.min_per_class)} per class · κ ≥ {String(latest.policy.min_kappa)} · FPR ≤ {pct(Number(latest.policy.max_fpr), 0)}. These are starting defaults, not universal truths.</p>
              {latest.reasons.length > 0 && <ul className="list-inside list-disc text-bad">{latest.reasons.map((r) => <li key={r}>{r}</li>)}</ul>}
              <p className="text-xs text-muted">Reference labels: {Object.entries(latest.reference_sources).map(([k, v]) => `${v} ${k}`).join(", ")} — <b>synthetic fixture labels, not human labels</b>.</p>
            </div>
          </div>
          {errors.length > 0 && (
            <details className="rounded border border-line"><summary className="cursor-pointer px-3 py-2 text-[13px] font-medium">Where the judge disagreed with the reference ({errors.length})</summary>
              <ul className="divide-y divide-line">{errors.slice(0, 12).map((e) => (
                <li key={e.item_id} className="space-y-0.5 px-3 py-2 text-[13px]"><div className="flex items-center gap-2"><span className="font-mono text-xs">{e.item_id}</span><Badge tone={e.reference_label ? "ok" : "bad"}>ref: {e.reference_label ? "pass" : "fail"}</Badge><Badge tone={e.predicted ? "ok" : "bad"}>judge: {e.predicted ? "pass" : "fail"}</Badge></div><p className="text-muted">{e.candidate_output}</p>{e.notes && <p className="text-xs text-faint">{e.notes}</p>}</li>))}</ul></details>)}
          {history.length > 1 && <div><div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-faint">Calibration history</div>
            <ul className="space-y-1 text-[13px]">{history.map((h) => <li key={h.id} className="flex flex-wrap items-center gap-2"><Badge tone={h.admitted ? "ok" : "bad"}>{h.admitted ? "admitted" : "not admitted"}</Badge><span className="num">n={h.n_items_used}</span><span className="num text-muted">κ {h.metrics.kappa.toFixed(2)} · FPR {pct(h.metrics.fpr)}</span><span className="text-faint">{shortDate(h.created_at)}</span>{h.reasons[0] && <span className="text-xs text-muted">— {h.reasons[0]}</span>}</li>)}</ul></div>}
        </div>
      )}
    </Card>
  );
}

export default async function JudgesPage() {
  try {
    const judges = await api.judges();
    const errs = await Promise.all(judges.map(async (j) => (j.latest ? (await api.calibrationItems((j.latest as unknown as CalRun).id)).items.filter((i) => i.predicted !== i.reference_label) : [])));
    return (
      <>
        <PageHeader title="Judge calibration" sub="An LLM judge is a model that must itself be evaluated. Only a judge whose exact configuration passed calibration may affect a release decision; everything else is diagnostic." right={<div className="flex items-center gap-2"><SyntheticBadge /><Link href="/judges/annotate" className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white hover:opacity-90">Annotate items →</Link></div>} />
        <div className="space-y-5">{judges.map((j, i) => <JudgeCard key={j.id} j={j} errors={errs[i] as never} />)}</div>
      </>
    );
  } catch (e) { return <ErrorState error={e} />; }
}

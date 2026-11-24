import { Card, CardHeader, PageHeader } from "@/components/ui";
import { GLOSSARY } from "@/lib/glossary";

export const metadata = { title: "Methodology" };

const LAYERS = [
  ["Outcome", "Did the task actually succeed? Final answer facts, forbidden claims, expected state/side effect, tests passing."],
  ["Trajectory", "Was the path reasonable? No duplicate identical calls, no loops, no error thrashing, context fetched before the dependent action."],
  ["Component / tool", "Were tools used correctly? Right tool, valid arguments, required tools used, forbidden tools avoided, step budget."],
  ["Policy / safety", "Hard constraints (never leak a secret, never refund a final-sale item). Always deterministic; never left to a judge alone."],
  ["Diagnostic trace checks", "Tool-choice quality, stopping behaviour, grounding. Informational until their evaluator has been calibrated."],
];

export default function MethodologyPage() {
  return (
    <>
      <PageHeader title="Methodology" sub="What the numbers mean, in plain language, and exactly where the evidence is weak. Use this page to explain the project in an interview." />
      <div className="grid gap-5 lg:grid-cols-2">
        <Card><CardHeader title="Agent quality is not one number" />
          <ul className="divide-y divide-line">{LAYERS.map(([k, v]) => <li key={k} className="px-4 py-2.5 text-[13px]"><b>{k}.</b> <span className="text-muted">{v}</span></li>)}</ul>
          <p className="px-4 pb-3 text-xs text-muted">A case passes only if <b>all required (gating) assertions pass</b>. No weighted average. Execution errors (timeouts, provider failures) are a separate status and never count as wrong answers.</p></Card>
        <Card><CardHeader title="How a regression decision is made" />
          <ol className="list-inside list-decimal space-y-1.5 px-4 py-3 text-[13px] text-muted">
            <li><b className="text-fg">Validate first.</b> Same dataset hash, fixture, sample counts, judge and model; complete runs; no hidden execution-error skew. Otherwise: INVALID COMPARISON (no statistics).</li>
            <li><b className="text-fg">Reduce to cases.</b> Repeated samples of one case are correlated, so each case becomes its pass fraction.</li>
            <li><b className="text-fg">Paired bootstrap over cases.</b> Resample matched cases with replacement 10,000×; take the 95% interval of the mean difference (candidate − baseline).</li>
            <li><b className="text-fg">Apply the margin.</b> Interval wholly above 0 → improvement. Wholly below −margin → regression. Lower bound ≥ −margin → no meaningful regression. Otherwise INCONCLUSIVE.</li>
            <li><b className="text-fg">Too few cases?</b> INCONCLUSIVE. “Not significant” is never read as “equivalent”.</li>
          </ol>
          <p className="px-4 pb-3 text-xs text-muted">McNemar and Wilson intervals are shown as diagnostics. With ~30 cases, intervals are wide; that is the honest answer.</p></Card>
        <Card><CardHeader title="Judges must be calibrated" />
          <p className="px-4 py-3 text-[13px] text-muted">A judge configuration is identified by <b className="text-fg">(backend, model, prompt hash)</b>. Default admission: ≥ 50 labelled items, ≥ 10 per class, Cohen’s κ ≥ 0.60, false-positive rate ≤ 5%. Change any identity part and you must calibrate again. CI refuses to gate on a judge that is not currently admitted. Seeded labels here are <b className="text-fg">synthetic fixture labels</b>, never presented as human.</p></Card>
        <Card><CardHeader title="Known limitations" />
          <ul className="list-inside list-disc space-y-1.5 px-4 py-3 text-[13px] text-muted">
            <li>The demo agents are scripted policy engines with seeded faults, not LLMs. Their numbers prove the machinery, not any model’s quality.</li>
            <li>Small datasets (10–30 cases) give wide intervals; the production policy needs ≥ 50 independent cases.</li>
            <li>The offline heuristic judge is a keyword matcher; it is calibrated like any other and can fail.</li>
            <li>Cost is an API-equivalent estimate from a configurable synthetic price table, never money spent.</li>
            <li>Annotator ids are self-declared handles (no authentication); labels are append-only and never alter reference labels or gates.</li>
          </ul></Card>
      </div>
      <h2 className="mb-3 mt-8 text-[15px] font-semibold">Glossary</h2>
      <dl className="grid gap-3 md:grid-cols-2">{GLOSSARY.map((g) => (
        <div key={g.term} className="rounded-lg border border-line bg-panel p-4"><dt className="text-[14px] font-semibold">{g.term}</dt><dd className="mt-1 text-[13px]">{g.short}</dd><dd className="mt-1 text-xs text-muted"><b>Why it matters:</b> {g.why}</dd></div>))}</dl>
    </>
  );
}

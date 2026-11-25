import { ExperimentCard } from "@/components/experiment-card";
import { RunsTable } from "@/components/runs-table";
import { Badge, Card, CardHeader, ErrorState, KindBadge, LiveNote, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { comparisonKind, EXPERIMENT_REPORT_PATH, PROOF_RUNS, splitKinds } from "@/lib/live";

export const metadata = { title: "Experiments" };
export const dynamic = "force-dynamic";

export default async function ExperimentsPage() {
  try {
    const [{ items }, comps] = await Promise.all([api.runs({ page_size: 100 }), api.comparisons()]);
    const live = comps.filter((c) => comparisonKind(c, items) === "live");
    const details = await Promise.all(live.map((c) => api.comparison(c.id)));
    // valid comparisons first; an INVALID one is shown too, with its reason, never hidden
    details.sort((a, b) => Number(b.valid) - Number(a.valid) || b.id - a.id);
    const split = splitKinds(items);
    return (
      <>
        <PageHeader title="Experiments" sub="Every evaluation run, with its pinned agent version, dataset hash and provenance. Filter by kind (live vs synthetic), agent, version, model, dataset, status or date." />

        {details.length > 0 && (
          <section aria-labelledby="exp001" className="mb-6 space-y-4">
            <div>
              <h2 id="exp001" className="flex flex-wrap items-center gap-2 text-[15px] font-semibold">Experiment 001 — research-agent reliability <KindBadge kind="live" /></h2>
              <p className="mt-1 text-xs text-muted">Full write-up in the repository: <code className="font-mono">{EXPERIMENT_REPORT_PATH}</code>. Sanitized machine-readable evidence ships in <code className="font-mono">evidence/experiments/001-research-agent-reliability/</code>; the comparison below is recomputed by the evaluator from those stored samples.</p>
            </div>
            <LiveNote />
            <div className="grid gap-4">{details.map((d) => <ExperimentCard key={d.id} comp={d} title={d.name} />)}</div>
            <Card><CardHeader title="CI regression-gate proofs (GitHub Actions)" sub="Four disposable pull requests exercised the real baseline/candidate path; runs are linked, the branches are deleted." />
              <ul className="divide-y divide-line text-[13px]">{PROOF_RUNS.map((p) => (
                <li key={p.n} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2"><span><b>{p.n}.</b> {p.what}</span>
                  <span className="flex items-center gap-2"><Badge tone={p.outcome === "pass" ? "ok" : "warn"}>{p.outcome === "pass" ? "passed" : "correctly rejected"}</Badge><a className="text-accent hover:underline" href={p.url} target="_blank" rel="noreferrer">workflow run ↗</a></span></li>))}</ul></Card>
          </section>
        )}

        <h2 className="mb-2 text-[13px] font-semibold">All runs <span className="font-normal text-muted">({split.synthetic.runs} synthetic · {split.live.runs} live — never aggregated together)</span></h2>
        <Card><RunsTable runs={items} /></Card>
      </>
    );
  } catch (e) { return <ErrorState error={e} />; }
}

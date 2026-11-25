import Link from "next/link";
import { FailureBars } from "@/components/charts";
import { Badge, Card, CardHeader, ErrorState, PageHeader } from "@/components/ui";
import { Trajectory } from "@/components/samples-table";
import { api } from "@/lib/api";
import { label } from "@/lib/format";

export const metadata = { title: "Failures" };
export const dynamic = "force-dynamic";
type Props = { searchParams: Promise<{ run?: string; baseline?: string }> };
const SEV = { critical: "bad", high: "warn", medium: "neutral", low: "neutral" } as const;

export default async function FailuresPage({ searchParams }: Props) {
  const q = await searchParams;
  try {
    const [runs, ov] = await Promise.all([api.runs({ page_size: 100 }), api.overview()]);
    const run = q.run ?? ov.candidate.id;
    const baseline = q.baseline ?? (q.run ? "" : ov.baseline.id);
    const f = await api.failures(run, baseline || undefined);
    return (
      <>
        <PageHeader title="What is actually breaking most often?" sub="Deterministic counts over stored assertion evidence, grouped by root-cause label. Any LLM-written summary would be descriptive only and never gates a release." />
        <form className="mb-4 flex flex-wrap items-end gap-3 text-xs">
          <label className="flex flex-col gap-1 font-medium text-faint">Run
            <select name="run" defaultValue={run} className="max-w-[320px] rounded border border-line bg-panel px-2 py-1.5 text-[13px] normal-case tracking-normal text-fg">{runs.items.filter((r) => r.n_samples).map((r) => <option key={r.id} value={r.id}>{r.execution_kind === "live" ? "[LIVE] " : "[synthetic] "}{r.name}</option>)}</select></label>
          <label className="flex flex-col gap-1 font-medium text-faint">Compare to
            <select name="baseline" defaultValue={baseline} className="max-w-[320px] rounded border border-line bg-panel px-2 py-1.5 text-[13px] normal-case tracking-normal text-fg"><option value="">(none)</option>{runs.items.map((r) => <option key={r.id} value={r.id}>{r.execution_kind === "live" ? "[LIVE] " : "[synthetic] "}{r.name}</option>)}</select></label>
          <button className="rounded border border-line bg-panel px-3 py-1.5 text-[13px] hover:bg-panel2">Apply</button>
        </form>
        <Card className="mb-5"><div className="p-4"><div className="text-[12px] font-medium text-muted">Summary (from stored evidence)</div><p className="mt-1 text-[15px]">{f.summary}</p>
          <p className="mt-2 text-xs text-muted">{f.n_failed_samples} failed samples · {f.n_execution_errors} execution errors (excluded from quality failures)</p></div></Card>
        <div className="grid gap-5 lg:grid-cols-[1fr_1.3fr]">
          <Card><CardHeader title="Failure modes" sub={baseline ? "Coloured = this run, grey = comparison run." : "Colour = severity."} />
            <div className="p-3">{f.clusters.length ? <FailureBars clusters={f.clusters} baseline={baseline ? f.clusters.map((c) => ({ ...c, count: c.baseline_count })) : undefined} /> : <p className="py-10 text-center text-sm text-muted">No failures in this run.</p>}</div></Card>
          <Card><CardHeader title="Clusters" />
            <ul className="divide-y divide-line">{f.clusters.map((c) => (
              <li key={c.label} className="space-y-2 px-4 py-3 text-[13px]">
                <div className="flex flex-wrap items-center gap-2"><span className="num text-lg font-semibold">{c.count}</span><span className="font-medium">{label(c.label)}</span>
                  <Badge tone={SEV[c.severity as keyof typeof SEV] ?? "neutral"}>{c.severity}</Badge>
                  {baseline && (c.new ? <Badge tone="bad">NEW vs comparison</Badge> : c.increased ? <Badge tone="bad">▲ +{c.delta}</Badge> : c.delta < 0 ? <Badge tone="ok">▼ {c.delta}</Badge> : <Badge>unchanged</Badge>)}
                  <span className="num text-xs text-muted">{(c.pct_of_failures * 100).toFixed(0)}% of failure labels</span></div>
                <p className="text-muted">{c.summary}</p>
                <div className="flex flex-wrap gap-1">{Object.entries(c.categories).map(([k, v]) => <Badge key={k}>{label(k)} · {v}</Badge>)}</div>
                <ul className="space-y-1">{c.examples.slice(0, 3).map((s) => (
                  <li key={s.id} className="flex flex-wrap items-center gap-2 rounded border border-line bg-panel2 px-2 py-1.5"><Link className="font-mono text-[12px] text-accent hover:underline" href={`/traces/${s.id}`}>{s.case_id} #{s.sample_index}</Link><Trajectory tools={s.tool_sequence} max={4} /></li>))}</ul>
              </li>))}</ul></Card>
        </div>
        <p className="mt-4 text-xs text-muted">{f.note}</p>
      </>
    );
  } catch (e) { return <ErrorState error={e} />; }
}

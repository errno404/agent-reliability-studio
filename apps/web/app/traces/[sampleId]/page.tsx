import Link from "next/link";
import { TraceWaterfall } from "@/components/trace-waterfall";
import { Trajectory } from "@/components/samples-table";
import { Badge, Card, CardHeader, Crumbs, ErrorState, PageHeader, StatusBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { label, ms, num } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function TracePage({ params }: { params: Promise<{ sampleId: string }> }) {
  const { sampleId } = await params;
  try {
    const [t, s] = await Promise.all([api.trace(Number(sampleId)), api.sample(Number(sampleId))]);
    return (
      <>
        <Crumbs items={[{ href: "/traces", label: "Traces" }, { href: `/experiments/${t.run_id}`, label: t.run_id }, { label: `${t.case_id} #${s.sample_index}` }]} />
        <PageHeader title={t.case_id} sub={<>Trace <code className="font-mono text-xs">{t.trace_id.slice(0, 16)}…</code> · sample {s.sample_index} · total {ms(t.total_ms)}</>} right={<div className="flex items-center gap-2"><StatusBadge status={s.status} />{s.failure_labels.map((l) => <Badge key={l} tone="bad">{label(l)}</Badge>)}</div>} />
        <Card className="mb-5"><CardHeader title="Trajectory" sub="Ordered tool calls (observable behaviour only)." />
          <div className="px-4 py-3"><Trajectory tools={t.trajectory} max={20} /></div></Card>
        <TraceWaterfall spans={t.spans} totalMs={t.total_ms} />
        <div className="mt-5 grid grid-cols-1 items-start gap-5 lg:grid-cols-2">
          <Card><CardHeader title="Input → output" />
            <div className="space-y-3 p-4 text-[13px]"><div><div className="mb-1 text-[12px] font-medium text-muted">Input</div><p className="whitespace-pre-wrap">{s.input_text}</p></div>
              <div><div className="mb-1 text-[12px] font-medium text-muted">Output</div><p className="whitespace-pre-wrap rounded bg-panel2 px-3 py-2">{s.final_output || "(empty)"}</p></div>
              <div className="num flex flex-wrap gap-3 text-xs text-muted"><span>{num(s.total_tokens)} tokens</span><span>{String(s.result.turns ?? 1)} turn(s)</span><span>{String(s.result.steps ?? 0)} steps</span></div></div></Card>
          <Card><CardHeader title="Why this status" sub={s.status_explanation} />
            <ul className="divide-y divide-line">{s.assertions.map((a) => (
              <li key={a.name} className="flex items-start gap-2 px-4 py-2 text-[13px]"><Badge tone={a.skipped ? "neutral" : a.passed ? "ok" : a.gating ? "bad" : "warn"}>{a.skipped ? "skip" : a.passed ? "pass" : "fail"}</Badge>
                <div><span className="font-mono text-[11.5px]">{a.type}</span> <span className="text-faint">· {a.layer}{a.gating ? "" : " · informational"}</span><div className="text-xs text-muted">{a.evidence}</div></div></li>))}</ul></Card>
        </div>
        <p className="mt-4 text-xs text-muted">Compare this trace across versions via a <Link className="text-accent hover:underline" href="/compare">comparison</Link>. Distil a failing trace into a candidate case with <code className="font-mono">ars traces distill</code>; candidates are never auto-promoted to a golden dataset.</p>
      </>
    );
  } catch (e) { return <ErrorState error={e} />; }
}

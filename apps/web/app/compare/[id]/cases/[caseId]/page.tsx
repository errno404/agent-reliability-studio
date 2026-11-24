import Link from "next/link";
import { Trajectory } from "@/components/samples-table";
import { Badge, Card, CardHeader, Crumbs, ErrorState, PageHeader, StatusBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { label, ms, num } from "@/lib/format";
import type { CaseDef, SampleDetail, TrajDiff } from "@/lib/types";

export const dynamic = "force-dynamic";

function Side({ title, tone, samples }: { title: string; tone: "neutral" | "info"; samples: SampleDetail[] }) {
  const s = samples[0];
  return (
    <Card className="min-w-0">
      <CardHeader title={<span className="flex items-center gap-2"><Badge tone={tone}>{title}</Badge>{s && <StatusBadge status={s.status} />}</span>}
        sub={samples.length > 1 ? `${samples.length} samples: ${samples.map((x) => x.status[0]).join(" ")}` : undefined} />
      {!s ? <p className="p-4 text-sm text-muted">This run has no sample for this case.</p> : (
        <div className="space-y-4 p-4 text-[13px]">
          <section><h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-faint">Input</h3><p className="whitespace-pre-wrap">{s.input_text}</p></section>
          <section><h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-faint">Output</h3><p className="whitespace-pre-wrap rounded bg-panel2 px-3 py-2">{s.final_output || <span className="text-faint">(empty)</span>}</p></section>
          <section><h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-faint">Tool sequence &amp; arguments</h3>
            <ol className="space-y-1 font-mono text-[11.5px]">{(s.result.tool_calls as { name: string; arguments: object; error?: string }[] | undefined ?? []).map((t, i) => (
              <li key={i} className="rounded border border-line px-2 py-1"><span className="font-semibold">{t.name}</span>{t.error && <span className="ml-2 text-bad">{t.error}</span>}<div className="break-all text-muted">{JSON.stringify(t.arguments)}</div></li>))}</ol>
          </section>
          <section><h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-faint">Assertions</h3>
            <ul className="space-y-1">{s.assertions.map((a) => (
              <li key={a.name} className="flex items-start gap-2"><Badge tone={a.skipped ? "neutral" : a.passed ? "ok" : a.gating ? "bad" : "warn"}>{a.skipped ? "skip" : a.passed ? "pass" : a.gating ? "FAIL" : "warn"}</Badge>
                <span><span className="font-mono text-[11.5px]">{a.type}</span> <span className="text-faint">· {a.layer}{!a.gating ? " · informational" : ""}</span><div className="text-xs text-muted">{a.evidence}</div></span></li>))}</ul>
          </section>
          <div className="num flex flex-wrap gap-3 text-xs text-muted"><span>{ms(s.latency_ms)}</span><span>{num(s.total_tokens)} tokens</span><Link className="text-accent hover:underline" href={`/traces/${s.id}`}>open trace →</Link></div>
        </div>)}
    </Card>
  );
}

export default async function CasePage({ params }: { params: Promise<{ id: string; caseId: string }> }) {
  const { id, caseId } = await params;
  try {
    const [cc, comp] = await Promise.all([api.caseComparison(Number(id), caseId), api.comparison(Number(id))]);
    const d = cc.diff as unknown as TrajDiff;
    const expected = cc.expected_assertions as unknown as CaseDef["assertions"];
    return (
      <>
        <Crumbs items={[{ href: "/compare", label: "Compare" }, { href: `/compare/${id}`, label: comp.name }, { label: caseId }]} />
        <PageHeader title={caseId} sub={cc.description} right={<Badge>{label(cc.category)}</Badge>} />
        <Card className="mb-5"><CardHeader title="Expected behaviour" sub="The assertions that define pass/fail for this case." />
          <ul className="grid gap-1.5 p-4 text-[13px] md:grid-cols-2">{expected.map((a, i) => (
            <li key={i} className="flex items-start gap-2"><Badge tone={a.gating === false ? "neutral" : "info"}>{a.layer}</Badge><span><span className="font-mono text-[11.5px]">{a.type}</span>{" "}<span className="text-muted">{JSON.stringify(Object.fromEntries(Object.entries(a).filter(([k, v]) => !["type", "layer", "gating", "severity", "label", "note"].includes(k) && v !== null))).slice(0, 140)}</span></span></li>))}</ul>
        </Card>
        <Card className="mb-5 border-accent/40"><CardHeader title="Diff" sub="Baseline → candidate, first sample." />
          <div className="space-y-3 p-4 text-[13px]">
            <div className="flex flex-wrap items-center gap-2">{d.changed_outcome ? <Badge tone="warn">outcome changed: {d.baseline_status} → {d.candidate_status}</Badge> : <Badge>outcome unchanged ({d.baseline_status})</Badge>}
              {d.added_tools?.map((t) => <Badge key={t} tone="info">+ {t}</Badge>)}{d.removed_tools?.map((t) => <Badge key={t} tone="neutral">− {t}</Badge>)}
              <span className="num text-muted">latency {d.latency_delta_ms >= 0 ? "+" : ""}{ms(d.latency_delta_ms)} · tokens {d.token_delta >= 0 ? "+" : ""}{num(d.token_delta)}</span></div>
            <div className="grid gap-2 md:grid-cols-2"><div><div className="text-[11px] font-semibold uppercase tracking-wider text-faint">Baseline trajectory</div><Trajectory tools={d.baseline ?? []} max={12} /></div><div><div className="text-[11px] font-semibold uppercase tracking-wider text-faint">Candidate trajectory</div><Trajectory tools={d.candidate ?? []} max={12} /></div></div>
            {d.changed_arguments?.map((c, i) => (
              <div key={i} className="rounded-md border border-warn/40 bg-warn-soft p-3"><div className="mb-1 font-semibold text-warn">Changed arguments to <span className="font-mono">{c.tool}</span></div>
                <div className="grid gap-2 font-mono text-xs md:grid-cols-2"><div><div className="mb-1 font-sans text-[10px] font-semibold uppercase tracking-wider text-faint">baseline</div><pre className="overflow-x-auto whitespace-pre-wrap rounded bg-panel p-2 text-muted">{JSON.stringify(c.baseline, null, 1)}</pre></div><div><div className="mb-1 font-sans text-[10px] font-semibold uppercase tracking-wider text-faint">candidate</div><pre className="overflow-x-auto whitespace-pre-wrap rounded bg-panel p-2">{JSON.stringify(c.candidate, null, 1)}</pre></div></div></div>))}
            {(d.assertions_newly_failing?.length ?? 0) > 0 && <div><span className="text-bad">Newly failing:</span> <span className="font-mono text-xs">{d.assertions_newly_failing?.join(", ")}</span></div>}
            {(d.assertions_fixed?.length ?? 0) > 0 && <div><span className="text-ok">Fixed:</span> <span className="font-mono text-xs">{d.assertions_fixed?.join(", ")}</span></div>}
          </div></Card>
        <div className="grid gap-5 xl:grid-cols-2"><Side title="BASELINE" tone="neutral" samples={cc.baseline} /><Side title="CANDIDATE" tone="info" samples={cc.candidate} /></div>
      </>
    );
  } catch (e) { return <ErrorState error={e} />; }
}

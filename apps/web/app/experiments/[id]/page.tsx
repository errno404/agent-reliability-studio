import Link from "next/link";
import { FailureBars } from "@/components/charts";
import { SamplesTable } from "@/components/samples-table";
import { Badge, Card, CardHeader, Crumbs, ErrorState, HashChip, PageHeader, Stat, StatusBadge, SyntheticBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { ms, num, pct, shortDate } from "@/lib/format";
import type { Summary } from "@/lib/types";

export const dynamic = "force-dynamic";
type Props = { params: Promise<{ id: string }>; searchParams: Promise<{ status?: string; category?: string; label?: string; page?: string }> };

export default async function RunPage({ params, searchParams }: Props) {
  const { id } = await params;
  const q = await searchParams;
  try {
    const [run, samples] = await Promise.all([api.run(id), api.samples(id, { status: q.status, category: q.category, label: q.label, page: q.page ?? 1, page_size: 40 })]);
    const s = run.summary as unknown as Summary;
    const m = run.manifest as Record<string, string | number | boolean | string[]>;
    const page = Number(q.page ?? 1);
    const qs = (p: number) => new URLSearchParams({ ...(q.status ? { status: q.status } : {}), ...(q.category ? { category: q.category } : {}), ...(q.label ? { label: q.label } : {}), page: String(p) }).toString();
    return (
      <>
        <Crumbs items={[{ href: "/experiments", label: "Experiments" }, { label: run.name }]} />
        <PageHeader title={run.name} sub={<>Run <code className="font-mono text-xs">{run.id}</code> · {shortDate(run.created_at)} · seed {run.seed}</>} right={<div className="flex gap-2"><StatusBadge status={run.status} />{run.is_synthetic && <SyntheticBadge />}</div>} />
        {run.error && <ErrorState error={new Error(run.error)} />}
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="Task success" value={pct(s.task_success.rate)} n={s.task_success.n} ciLo={s.task_success.ci_low} ciHi={s.task_success.ci_high} />
          <Stat label="pass^k / pass@k" value={`${pct(s.pass_hat_k, 0)} / ${pct(s.pass_at_k, 0)}`} sub={`k=${s.k}`} />
          <Stat label="Flaky cases" value={s.flaky_cases.length} sub="pass AND fail across repeats" />
          <Stat label="Execution errors" value={String(s.status_counts.execution_error ?? 0)} sub="not quality failures" />
        </div>
        <div className="mt-5 grid gap-5 lg:grid-cols-2">
          <Card><CardHeader title="Pinned identity" sub="Everything that must match for a fair comparison." />
            <dl className="grid grid-cols-[130px_1fr] gap-x-3 gap-y-2 p-4 text-[13px]">
              <dt className="text-muted">Agent</dt><dd>{run.agent} <Badge>{run.agent_version}</Badge></dd>
              <dt className="text-muted">Model</dt><dd className="font-mono text-xs">{run.model}</dd>
              <dt className="text-muted">Agent code hash</dt><dd><HashChip value={run.agent_hash} /></dd>
              <dt className="text-muted">Prompt hash</dt><dd><HashChip value={run.prompt_hash} /></dd>
              <dt className="text-muted">Tool schema hash</dt><dd><HashChip value={run.tool_schema_hash} /></dd>
              <dt className="text-muted">Dataset</dt><dd>{run.dataset}:{run.dataset_version} <HashChip value={run.dataset_hash} /></dd>
              <dt className="text-muted">Fixture hash</dt><dd><HashChip value={String(m.fixture_hash ?? "")} /></dd>
              <dt className="text-muted">Judge</dt><dd>{run.judge ? <>{run.judge} <Badge tone={run.judge_admitted ? "ok" : "warn"}>{run.judge_admitted ? "calibrated" : "diagnostic only"}</Badge></> : "none (deterministic assertions only)"}</dd>
              <dt className="text-muted">Git</dt><dd><HashChip value={String(m.git_commit ?? "")} />{m.git_dirty ? <Badge tone="warn" className="ml-2">dirty tree</Badge> : null}</dd>
              <dt className="text-muted">Evaluator</dt><dd className="font-mono text-xs">{String(m.evaluator_version)} · py {String(m.python_version)}</dd>
            </dl>
          </Card>
          <Card><CardHeader title="Failure modes" sub={`${s.n_samples} samples; ${num(Object.values(s.failure_labels).reduce((a, b) => a + b, 0))} labels`} />
            <div className="p-3">{run.clusters.length ? <FailureBars clusters={run.clusters as never} /> : <p className="px-2 py-6 text-center text-sm text-muted">No failures.</p>}</div>
          </Card>
        </div>
        <Card className="mt-5">
          <CardHeader title="Samples" sub={`${samples.total} matching · latency ${ms(s.latency_p50_ms)} p50 / ${ms(s.latency_p95_ms)} p95`}
            right={<form className="flex flex-wrap items-center gap-2 text-xs"><select name="status" defaultValue={q.status ?? ""} className="rounded border border-line bg-panel px-2 py-1"><option value="">any status</option>{["passed", "failed", "execution_error"].map((x) => <option key={x}>{x}</option>)}</select><button className="rounded border border-line px-2 py-1 hover:bg-panel2">Filter</button></form>} />
          <SamplesTable samples={samples.items} />
          <div className="flex items-center justify-between border-t border-line px-4 py-2 text-xs text-muted">
            <span>Page {page} · {samples.total} total</span>
            <span className="flex gap-3">{page > 1 && <Link className="text-accent" href={`?${qs(page - 1)}`}>← Prev</Link>}{page * 40 < samples.total && <Link className="text-accent" href={`?${qs(page + 1)}`}>Next →</Link>}</span>
          </div>
        </Card>
      </>
    );
  } catch (e) { return <ErrorState error={e} />; }
}

import Link from "next/link";
import { Badge, Card, CardHeader, ErrorState, HashChip, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { label } from "@/lib/format";

export const metadata = { title: "Datasets" };
export const dynamic = "force-dynamic";

export default async function DatasetsPage() {
  try {
    const [ds, cands] = await Promise.all([api.datasets(), api.candidates()]);
    return (
      <>
        <PageHeader title="Datasets" sub="Golden datasets are versioned evidence. A published version is frozen: any change to a case, fixture, rubric or tool requirement changes its hash, so it must become a new version." />
        <div className="grid gap-4 md:grid-cols-2">
          {ds.map((d) => (
            <Link key={d.id} href={`/datasets/${d.dataset}/${d.version}`} className="block rounded-lg border border-line bg-panel p-4 transition-colors hover:border-accent/60">
              <div className="flex flex-wrap items-center gap-2"><h2 className="text-[15px] font-semibold">{d.dataset}:{d.version}</h2>
                {d.published ? <Badge tone="ok" title="Published datasets are frozen">🔒 published · frozen</Badge> : <Badge tone="warn">draft · editable</Badge>}<Badge>{d.kind}</Badge></div>
              <p className="mt-1 line-clamp-2 text-sm text-muted">{d.description}</p>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs"><Badge tone="info">{d.case_count} cases</Badge><HashChip label="dataset" value={d.hash} /><HashChip label="fixture" value={d.fixture_hash} /></div>
              <div className="mt-2 flex flex-wrap gap-1">{Object.entries(d.categories).map(([k, v]) => <Badge key={k}>{label(k)} · {v}</Badge>)}</div>
            </Link>))}
        </div>
        <Card className="mt-6"><CardHeader title="Candidate cases (trace → case distillation)" sub="Suggested from traces; never auto-promoted. Review → edit → publish as a NEW dataset version." />
          {cands.length === 0 ? <p className="px-4 py-6 text-sm text-muted">No candidates yet. Create some with <code className="font-mono">ars traces distill --run RUN_ID</code>.</p> : (
            <ul className="divide-y divide-line">{cands.map((c) => (
              <li key={c.id} className="px-4 py-3 text-[13px]"><div className="flex flex-wrap items-center gap-2"><span className="font-mono text-xs font-medium">{String(c.case.id)}</span><Badge tone="warn">{c.status}</Badge></div>
                <p className="mt-1 text-muted">{String(c.case.description)}</p></li>))}</ul>)}
        </Card>
      </>
    );
  } catch (e) { return <ErrorState error={e} />; }
}

import { CaseList } from "@/components/case-list";
import { Badge, Card, CardHeader, Crumbs, ErrorState, HashChip, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { label } from "@/lib/format";
import type { CaseDef } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function DatasetPage({ params }: { params: Promise<{ name: string; version: string }> }) {
  const { name, version } = await params;
  try {
    const d = await api.dataset(name, version);
    const cases = d.cases.map((c) => ({ ...c, definition: c.definition as unknown as CaseDef }));
    return (
      <>
        <Crumbs items={[{ href: "/datasets", label: "Datasets" }, { label: `${name}:${version}` }]} />
        <PageHeader title={`${d.dataset}:${d.version}`} sub={d.description} right={d.published ? <Badge tone="ok">🔒 published · frozen</Badge> : <Badge tone="warn">draft · editable</Badge>} />
        <div className="mb-5 grid gap-4 md:grid-cols-[1fr_1.4fr]">
          <Card><CardHeader title="Provenance" />
            <dl className="grid grid-cols-[120px_1fr] gap-y-2 p-4 text-[13px]"><dt className="text-muted">Dataset hash</dt><dd><HashChip value={d.hash} /> <span className="font-mono text-[11px] text-faint">{d.hash}</span></dd>
              <dt className="text-muted">Fixture</dt><dd>{d.fixture_version} <HashChip value={d.fixture_hash} /></dd><dt className="text-muted">Source file</dt><dd className="font-mono text-xs">{d.source_path}</dd>
              <dt className="text-muted">Cases</dt><dd>{d.case_count}</dd></dl></Card>
          <Card><CardHeader title="Categories" /><div className="flex flex-wrap gap-2 p-4">{Object.entries(d.categories).map(([k, v]) => <Badge key={k} tone="info">{label(k)} · {v}</Badge>)}</div>
            <p className="px-4 pb-4 text-xs text-muted">Validate locally: <code className="font-mono">ars dataset validate {d.source_path}</code></p></Card>
        </div>
        <Card><CardHeader title="Case definitions" sub="Every case states why it exists. Expand a row for assertions, fixture and rubric." /><CaseList cases={cases} /></Card>
      </>
    );
  } catch (e) { return <ErrorState error={e} />; }
}

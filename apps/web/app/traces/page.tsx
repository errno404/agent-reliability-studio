import Link from "next/link";
import { SamplesTable } from "@/components/samples-table";
import { Card, CardHeader, ErrorState, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";

export const metadata = { title: "Traces" };
export const dynamic = "force-dynamic";
type Props = { searchParams: Promise<{ run_id?: string; status?: string; page?: string }> };

export default async function TracesPage({ searchParams }: Props) {
  const q = await searchParams;
  try {
    const [runs, traces] = await Promise.all([api.runs({ page_size: 100 }), api.traces({ run_id: q.run_id, status: q.status, page: q.page ?? 1, page_size: 30 })]);
    const page = Number(q.page ?? 1);
    return (
      <>
        <PageHeader title="Traces" sub="Every sample is an OpenTelemetry trace: agent → model calls → tool calls, with timing, tokens and errors. Open one to see the waterfall." />
        <Card>
          <CardHeader title={`${traces.total} traces`} right={
            <form className="flex flex-wrap items-center gap-2 text-xs">
              <select name="run_id" defaultValue={q.run_id ?? ""} className="max-w-[260px] rounded border border-line bg-panel px-2 py-1" aria-label="Run"><option value="">all runs</option>{runs.items.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</select>
              <select name="status" defaultValue={q.status ?? ""} className="rounded border border-line bg-panel px-2 py-1" aria-label="Status"><option value="">any status</option>{["passed", "failed", "execution_error"].map((s) => <option key={s}>{s}</option>)}</select>
              <button className="rounded border border-line px-2 py-1 hover:bg-panel2">Filter</button>
            </form>} />
          <SamplesTable samples={traces.items} />
          <div className="flex justify-between border-t border-line px-4 py-2 text-xs text-muted"><span>Page {page}</span>
            <span className="flex gap-3">{page > 1 && <Link className="text-accent" href={`?${new URLSearchParams({ ...(q.run_id ? { run_id: q.run_id } : {}), ...(q.status ? { status: q.status } : {}), page: String(page - 1) })}`}>← Prev</Link>}
              {page * 30 < traces.total && <Link className="text-accent" href={`?${new URLSearchParams({ ...(q.run_id ? { run_id: q.run_id } : {}), ...(q.status ? { status: q.status } : {}), page: String(page + 1) })}`}>Next →</Link>}</span></div>
        </Card>
      </>
    );
  } catch (e) { return <ErrorState error={e} />; }
}

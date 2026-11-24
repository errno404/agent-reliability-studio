import { RunsTable } from "@/components/runs-table";
import { Card, ErrorState, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";

export const metadata = { title: "Experiments" };
export const dynamic = "force-dynamic";

export default async function ExperimentsPage() {
  try {
    const { items } = await api.runs({ page_size: 100 });
    return (
      <>
        <PageHeader title="Experiments" sub="Every evaluation run, with its pinned agent version, dataset hash and provenance. Filter by agent, version, model, dataset, status or date." />
        <Card><RunsTable runs={items} /></Card>
      </>
    );
  } catch (e) { return <ErrorState error={e} />; }
}

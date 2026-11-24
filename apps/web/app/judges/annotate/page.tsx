import { AnnotateClient } from "@/components/annotate-client";
import { Crumbs, ErrorState, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";

export const metadata = { title: "Annotate" };
export const dynamic = "force-dynamic";

export default async function AnnotatePage() {
  try {
    const summary = await api.annotationSummary();
    return (
      <>
        <Crumbs items={[{ href: "/judges", label: "Judges" }, { label: "Annotate" }]} />
        <PageHeader title="Human annotation" sub="Label calibration items blind. Shortcuts: P pass · F fail · S skip. Labels are append-only; with two or more annotators we compute inter-annotator agreement and queue disagreements for adjudication." />
        <AnnotateClient initial={summary} />
      </>
    );
  } catch (e) { return <ErrorState error={e} />; }
}

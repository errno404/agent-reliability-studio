import Link from "next/link";
import { Badge, Card, DecisionBadge, Delta, ErrorState, KindBadge, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { pts, shortDate } from "@/lib/format";
import { comparisonKind, intentLabel, type Kind } from "@/lib/live";
import type { ComparisonOut } from "@/lib/types";

export const metadata = { title: "Compare" };
export const dynamic = "force-dynamic";

function CompareCard({ c, kind }: { c: ComparisonOut; kind: Kind | "mixed" }) {
  return (
    <Link href={`/compare/${c.id}`} className="block rounded-lg border border-line bg-panel p-4 transition-colors hover:border-accent/60">
      <div className="flex flex-wrap items-center justify-between gap-2"><span className="flex flex-wrap items-center gap-2"><DecisionBadge decision={c.decision} /><KindBadge kind={kind} /></span><span className="text-xs text-faint">{shortDate(c.created_at)}</span></div>
      <h2 className="mt-2 text-[15px] font-semibold">{c.name}</h2>
      <p className="mt-1 line-clamp-3 text-sm text-muted">{c.explanation}</p>
      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
        <Badge>{c.baseline_label}</Badge><span className="text-faint">→</span><Badge tone="info">{c.candidate_label}</Badge>
        {c.delta !== null && <span className="num ml-auto">Δ <Delta v={c.delta} /> pts</span>}
        <Badge tone={c.gate_verdict === "pass" ? "ok" : "bad"}>gate {c.gate_verdict}</Badge>
        <Badge>policy {c.policy_name}</Badge>
        <Badge tone={c.mode === "strict" ? "ok" : "warn"} title="Only strict comparisons can authorise a release">{c.mode}</Badge>
        <Badge title="What the author declared changed">intent: {intentLabel(c.intent)}</Badge>
      </div>
      {c.delta !== null && <div className="sr-only">{pts(c.delta)}</div>}
    </Link>
  );
}

export default async function CompareIndex() {
  try {
    const [comps, runs] = await Promise.all([api.comparisons(), api.runs({ page_size: 100 })]);
    const tagged = comps.map((c) => ({ c, kind: comparisonKind(c, runs.items) }));
    const groups: { key: Kind | "mixed"; title: string; note: string }[] = [
      { key: "live", title: "Live comparisons (real model)", note: "Real LLM behaviour evaluated in a controlled synthetic environment. Never blended with the synthetic demo." },
      { key: "synthetic", title: "Synthetic comparisons (scripted, seeded)", note: "Reference agents with injected faults; the measurement machinery is real, the agents are stand-ins." },
      { key: "mixed", title: "Mixed-kind pairs", note: "A synthetic run against a live run is never a valid comparison." },
    ];
    return (
      <>
        <PageHeader title="Compare" sub="Baseline vs candidate, validated before any statistics are computed. Every outcome is a legitimate result: improvement, no meaningful regression, regression, inconclusive, or an invalid comparison." />
        <div className="space-y-6">
          {groups.map((g) => {
            const rows = tagged.filter((t) => t.kind === g.key);
            if (!rows.length) return null;
            return (
              <section key={g.key} aria-labelledby={`grp-${g.key}`}>
                <h2 id={`grp-${g.key}`} className="mb-1 text-[13px] font-semibold">{g.title} <span className="font-normal text-muted">({rows.length})</span></h2>
                <p className="mb-3 text-xs text-muted">{g.note}</p>
                <div className="grid gap-3 md:grid-cols-2">{rows.map(({ c, kind }) => <CompareCard key={c.id} c={c} kind={kind} />)}</div>
              </section>
            );
          })}
        </div>
      </>
    );
  } catch (e) { return <ErrorState error={e} />; }
}
export const _unused = Card;

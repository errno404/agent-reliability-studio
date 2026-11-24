import Link from "next/link";
import { Badge, Card, DecisionBadge, Delta, ErrorState, PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { pts, shortDate } from "@/lib/format";

export const metadata = { title: "Compare" };
export const dynamic = "force-dynamic";

export default async function CompareIndex() {
  try {
    const comps = await api.comparisons();
    return (
      <>
        <PageHeader title="Compare" sub="Baseline vs candidate, validated before any statistics are computed. Every outcome is a legitimate result: improvement, no meaningful regression, regression, inconclusive, or an invalid comparison." />
        <div className="grid gap-3 md:grid-cols-2">
          {comps.map((c) => (
            <Link key={c.id} href={`/compare/${c.id}`} className="block rounded-lg border border-line bg-panel p-4 transition-colors hover:border-accent/60">
              <div className="flex flex-wrap items-center justify-between gap-2"><DecisionBadge decision={c.decision} /><span className="text-xs text-faint">{shortDate(c.created_at)}</span></div>
              <h2 className="mt-2 text-[15px] font-semibold">{c.name}</h2>
              <p className="mt-1 line-clamp-3 text-sm text-muted">{c.explanation}</p>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                <Badge>{c.baseline_label}</Badge><span className="text-faint">→</span><Badge tone="info">{c.candidate_label}</Badge>
                {c.delta !== null && <span className="num ml-auto">Δ <Delta v={c.delta} /> pts</span>}
                <Badge tone={c.gate_verdict === "pass" ? "ok" : "bad"}>gate {c.gate_verdict}</Badge>
                <Badge>policy {c.policy_name}</Badge>
              </div>
              {c.delta !== null && <div className="sr-only">{pts(c.delta)}</div>}
            </Link>
          ))}
        </div>
      </>
    );
  } catch (e) { return <ErrorState error={e} />; }
}
export const _unused = Card;

import Link from "next/link";
import { Badge, Card, CardHeader, DecisionBadge, ErrorState, PageHeader, SyntheticBadge } from "@/components/ui";
import { CiPlot } from "@/components/charts";
import { api } from "@/lib/api";
import { pts, shortDate } from "@/lib/format";

export const metadata = { title: "CI / Release Gates" };
export const dynamic = "force-dynamic";

export default async function GatesPage() {
  try {
    const [gates, policies] = await Promise.all([api.gates(), api.policies()]);
    const latest = gates[0];
    return (
      <>
        <PageHeader title="CI / Release gates" sub="The gate never weakens a threshold to turn green. It blocks on an invalid comparison, a meaningful regression, an uncalibrated judge, and (under the conservative policy) inconclusive evidence." right={<SyntheticBadge />} />
        {latest && (
          <Card className={latest.verdict === "pass" ? "border-ok/40" : "border-bad/40"}>
            <div className="grid gap-4 p-4 lg:grid-cols-[1.2fr_1fr]">
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-2"><span className={`rounded px-2.5 py-1 text-sm font-bold tracking-wide ${latest.verdict === "pass" ? "bg-ok-soft text-ok" : "bg-bad-soft text-bad"}`}>GATE {latest.verdict.toUpperCase()}</span><DecisionBadge decision={latest.decision} /><Badge>{latest.valid ? "comparison valid" : "comparison INVALID"}</Badge><Badge tone={latest.judge_ok ? "ok" : "bad"}>{latest.judge_ok ? "judges admitted" : "judge not admitted"}</Badge></div>
                <p className="text-[15px]">{latest.explanation}</p>
                <ul className="list-inside list-disc text-sm text-muted">{latest.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
                <Link className="text-sm font-medium text-accent hover:underline" href={`/compare/${latest.comparison_id}`}>{latest.comparison_name} →</Link>
              </div>
              <div>{latest.delta !== null && latest.ci_low !== null && latest.ci_high !== null && latest.margin !== null ? <CiPlot delta={latest.delta} lo={latest.ci_low} hi={latest.ci_high} margin={latest.margin} /> : <p className="text-sm text-muted">No interval: the comparison was invalid, so no statistics were computed.</p>}
                <p className="num mt-1 text-xs text-muted">margin −{((latest.margin ?? 0) * 100).toFixed(0)} pts · {latest.changed_cases} changed cases · policy {latest.policy_name}</p></div>
            </div>
          </Card>)}
        <Card className="mt-5"><CardHeader title="Decision history" sub="Each row is a stored comparison + gate decision." />
          <div className="scroll-x"><table className="w-full min-w-[820px] text-[13px]"><thead className="border-b border-line text-[11px] text-faint"><tr>{["Comparison", "Verdict", "Statistical result", "Δ", "Policy", "Reasons", "When"].map((h) => <th key={h} className="px-3 py-2 text-left font-medium">{h}</th>)}</tr></thead>
            <tbody className="divide-y divide-line">{gates.map((g) => (
              <tr key={g.id} className="align-top hover:bg-panel2"><td className="px-3 py-2"><Link className="font-medium text-accent hover:underline" href={`/compare/${g.comparison_id}`}>{g.comparison_name}</Link></td>
                <td className="px-3 py-2"><Badge tone={g.verdict === "pass" ? "ok" : "bad"}>{g.verdict.toUpperCase()}</Badge></td><td className="px-3 py-2"><DecisionBadge decision={g.decision} /></td>
                <td className="num px-3 py-2">{pts(g.delta)}</td><td className="px-3 py-2 text-muted">{g.policy_name}</td>
                <td className="max-w-[360px] px-3 py-2 text-xs text-muted">{g.reasons.join(" · ")}</td><td className="px-3 py-2 text-xs text-faint">{shortDate(g.created_at)}</td></tr>))}</tbody></table></div></Card>
        <Card className="mt-5"><CardHeader title="Statistical policies" sub="Defaults are conservative starting points, not universal constants. Each comparison stores the policy it used." />
          <div className="scroll-x"><table className="w-full text-[13px]"><thead className="border-b border-line text-[11px] text-faint"><tr>{["Policy", "Min matched cases", "α", "Bootstrap resamples", "Regression margin"].map((h) => <th key={h} className="px-3 py-2 text-left font-medium">{h}</th>)}</tr></thead>
            <tbody className="divide-y divide-line">{Object.entries(policies).map(([k, p]) => <tr key={k}><td className="px-3 py-2 font-mono text-xs">{k}</td><td className="num px-3 py-2">{p.min_cases}</td><td className="num px-3 py-2">{p.alpha}</td><td className="num px-3 py-2">{p.n_boot.toLocaleString()}</td><td className="num px-3 py-2">−{(p.margin * 100).toFixed(0)} pts</td></tr>)}</tbody></table></div>
          <p className="px-4 py-3 text-xs text-muted">The <code>demo-*</code> policies lower the minimum case count because the bundled synthetic datasets have 10–30 cases; <code>production</code> requires 50. Under <code>production</code>, the 30-case support comparison is correctly INCONCLUSIVE.</p></Card>
      </>
    );
  } catch (e) { return <ErrorState error={e} />; }
}

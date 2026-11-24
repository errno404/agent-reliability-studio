"use client";

import { Bar, BarChart, CartesianGrid, Cell, ErrorBar, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { label as fmtLabel, pct } from "@/lib/format";
import type { CategoryDelta, Cluster, TrendPoint } from "@/lib/types";

const AXIS = { fontSize: 11, fill: "var(--muted)" };
const GRID = "var(--line)";
const TIP = { background: "var(--panel)", border: "1px solid var(--line)", borderRadius: 6, fontSize: 12, color: "var(--fg)" };

/** Pass rate per agent version with Wilson 95% CI whiskers. A data table backs the chart for screen readers. */
export function TrendChart({ points }: { points: TrendPoint[] }) {
  const agents = [...new Set(points.map((p) => p.agent))];
  const versions = [...new Set(points.map((p) => p.version))].sort();
  const data = agents.map((a) => {
    const row: Record<string, number | string> = { agent: a };
    for (const v of versions) {
      const p = points.find((x) => x.agent === a && x.version === v);
      if (p) { row[v] = p.rate; row[`${v}_err`] = [p.rate - p.ci_low, p.ci_high - p.rate] as unknown as number; }
    }
    return row;
  });
  const colors: Record<string, string> = { v1: "var(--faint)", v2: "var(--accent)" };
  return (
    <figure aria-label="Task success rate by agent version, with 95% confidence intervals">
      <div className="h-64 w-full">
        <ResponsiveContainer>
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -12 }} barGap={4}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="agent" tick={AXIS} axisLine={false} tickLine={false} />
            <YAxis domain={[0, 1]} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} tick={AXIS} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={TIP} formatter={(v) => pct(Number(v), 1)} cursor={{ fill: "var(--panel-2)" }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            {versions.map((v) => (
              <Bar key={v} dataKey={v} name={`${v}${v === "v1" ? " (baseline)" : v === "v2" ? " (candidate)" : ""}`} fill={colors[v] ?? "var(--info)"} radius={[3, 3, 0, 0]}>
                <ErrorBar dataKey={`${v}_err`} width={4} stroke="var(--fg)" strokeWidth={1} direction="y" />
              </Bar>
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
      <table className="sr-only"><caption>Task success by agent version</caption><tbody>
        {points.map((p) => <tr key={p.run_id}><td>{p.agent} {p.version}</td><td>{pct(p.rate)}</td><td>{`95% CI ${pct(p.ci_low)} to ${pct(p.ci_high)}, n=${p.n}`}</td></tr>)}
      </tbody></table>
    </figure>
  );
}

const SEV_COLOR: Record<string, string> = { critical: "var(--bad)", high: "var(--warn)", medium: "var(--accent)", low: "var(--faint)" };

export function FailureBars({ clusters, baseline }: { clusters: Cluster[]; baseline?: Cluster[] }) {
  const base = new Map((baseline ?? []).map((c) => [c.label, c.count]));
  const data = clusters.slice(0, 8).map((c) => ({ name: fmtLabel(c.label), count: c.count, base: base.get(c.label) ?? 0, severity: c.severity }));
  return (
    <figure aria-label="Failure modes by count">
      <div style={{ height: Math.max(180, data.length * 34 + 30) }} className="w-full">
        <ResponsiveContainer>
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid stroke={GRID} horizontal={false} />
            <XAxis type="number" tick={AXIS} axisLine={false} tickLine={false} allowDecimals={false} />
            <YAxis type="category" dataKey="name" width={150} tick={AXIS} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={TIP} cursor={{ fill: "var(--panel-2)" }} />
            {baseline && <Bar dataKey="base" name="baseline" fill="var(--line)" radius={[0, 3, 3, 0]} barSize={8} />}
            <Bar dataKey="count" name="candidate" radius={[0, 3, 3, 0]} barSize={baseline ? 8 : 14}>
              {data.map((d, i) => <Cell key={i} fill={SEV_COLOR[d.severity] ?? "var(--accent)"} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <table className="sr-only"><caption>Failure counts</caption><tbody>
        {data.map((d) => <tr key={d.name}><td>{d.name}</td><td>{d.count}</td><td>{d.severity}</td></tr>)}
      </tbody></table>
    </figure>
  );
}

export function CategoryDeltaBars({ deltas }: { deltas: Record<string, CategoryDelta> }) {
  const data = Object.entries(deltas).filter(([, d]) => d.delta !== null).map(([k, d]) => ({ name: fmtLabel(k), delta: (d.delta ?? 0) * 100, n: d.n_candidate }))
    .sort((a, b) => a.delta - b.delta);
  return (
    <figure aria-label="Pass-rate change by category in percentage points">
      <div style={{ height: Math.max(160, data.length * 30 + 30) }} className="w-full">
        <ResponsiveContainer>
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid stroke={GRID} horizontal={false} />
            <XAxis type="number" tick={AXIS} axisLine={false} tickLine={false} unit=" pts" />
            <YAxis type="category" dataKey="name" width={110} tick={AXIS} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={TIP} formatter={(v) => `${Number(v) >= 0 ? "+" : ""}${Number(v).toFixed(1)} pts`} cursor={{ fill: "var(--panel-2)" }} />
            <Bar dataKey="delta" name="Δ pass rate" radius={3} barSize={14}>
              {data.map((d, i) => <Cell key={i} fill={d.delta < 0 ? "var(--bad)" : d.delta > 0 ? "var(--ok)" : "var(--faint)"} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <table className="sr-only"><caption>Pass-rate change by category</caption><tbody>
        {data.map((d) => <tr key={d.name}><td>{d.name}</td><td>{d.delta.toFixed(1)} pts</td><td>n={d.n}</td></tr>)}
      </tbody></table>
    </figure>
  );
}

/** Delta with its confidence interval drawn against zero and the non-inferiority margin (SVG, no chart lib). */
export function CiPlot({ delta, lo, hi, margin }: { delta: number; lo: number; hi: number; margin: number }) {
  const pad = 0.1;
  const min = Math.min(lo, -margin, 0) - pad * 0.5;
  const max = Math.max(hi, 0) + pad * 0.5;
  const W = 520, H = 92, L = 14, R = 14;
  const x = (v: number) => L + ((v - min) / (max - min)) * (W - L - R);
  const ticks = [-0.2, -0.1, 0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1].filter((t) => t >= min && t <= max);
  const desc = `Delta ${(delta * 100).toFixed(1)} points, 95% interval ${(lo * 100).toFixed(1)} to ${(hi * 100).toFixed(1)}, margin −${(margin * 100).toFixed(0)}.`;
  return (
    <figure aria-label={desc}>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-[560px]" role="img">
        <title>{desc}</title>
        <rect x={x(min)} y={14} width={Math.max(0, x(-margin) - x(min))} height={34} fill="var(--bad-soft)" />
        <line x1={x(0)} x2={x(0)} y1={8} y2={54} stroke="var(--fg)" strokeWidth={1} />
        <line x1={x(-margin)} x2={x(-margin)} y1={8} y2={54} stroke="var(--bad)" strokeWidth={1.25} strokeDasharray="4 3" />
        <line x1={x(lo)} x2={x(hi)} y1={31} y2={31} stroke="var(--accent)" strokeWidth={3} strokeLinecap="round" />
        <line x1={x(lo)} x2={x(lo)} y1={24} y2={38} stroke="var(--accent)" strokeWidth={2} />
        <line x1={x(hi)} x2={x(hi)} y1={24} y2={38} stroke="var(--accent)" strokeWidth={2} />
        <circle cx={x(delta)} cy={31} r={5} fill="var(--panel)" stroke="var(--accent)" strokeWidth={2.5} />
        {ticks.map((t) => <text key={t} x={x(t)} y={70} textAnchor="middle" fontSize={10} fill="var(--faint)">{t > 0 ? "+" : ""}{Math.round(t * 100)}</text>)}
        <text x={x(-margin)} y={88} textAnchor="start" fontSize={9.5} fill="var(--bad)">▲ −{Math.round(margin * 100)} pt non-inferiority margin</text>
        <text x={x(0) + 4} y={9} textAnchor="start" fontSize={9.5} fill="var(--muted)">no change</text>
      </svg>
    </figure>
  );
}

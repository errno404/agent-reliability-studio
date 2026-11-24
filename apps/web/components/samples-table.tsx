import Link from "next/link";
import { Badge, EmptyState, StatusBadge } from "@/components/ui";
import { label, ms, num } from "@/lib/format";
import type { SampleOut } from "@/lib/types";

export function Trajectory({ tools, max = 6 }: { tools: string[]; max?: number }) {
  if (!tools.length) return <span className="text-faint">(no tool calls)</span>;
  const shown = tools.slice(0, max);
  return (
    <span className="font-mono text-[11.5px] text-muted">
      {shown.map((t, i) => <span key={i}>{i > 0 && <span className="px-1 text-faint">→</span>}{t}</span>)}
      {tools.length > max && <span className="text-faint"> +{tools.length - max}</span>}
    </span>
  );
}

export function SamplesTable({ samples, linkCase }: { samples: SampleOut[]; linkCase?: (s: SampleOut) => string | null }) {
  if (!samples.length) return <EmptyState title="No samples match">Adjust the filters.</EmptyState>;
  return (
    <div className="scroll-x">
      <table className="w-full min-w-[820px] text-left text-[13px]">
        <thead className="border-b border-line text-[11px] uppercase tracking-wider text-faint">
          <tr>{["Case", "#", "Status", "Failure labels", "Trajectory", "Latency", "Tokens", ""].map((h) => <th key={h} scope="col" className="px-3 py-2 font-medium">{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-line">
          {samples.map((s) => (
            <tr key={s.id} className="align-top hover:bg-panel2">
              <td className="px-3 py-2"><div className="font-medium">{linkCase?.(s) ? <Link className="text-accent hover:underline" href={linkCase(s)!}>{s.case_id}</Link> : s.case_id}</div><div className="text-[11px] text-faint">{s.category}</div></td>
              <td className="num px-3 py-2">{s.sample_index}</td>
              <td className="px-3 py-2"><StatusBadge status={s.status} />{s.error_kind && <div className="mt-1 text-[11px] text-warn">{s.error_kind}</div>}</td>
              <td className="px-3 py-2"><div className="flex max-w-[220px] flex-wrap gap-1">{s.failure_labels.map((l) => <Badge key={l} tone={l === "execution_error" ? "warn" : "bad"}>{label(l)}</Badge>)}</div></td>
              <td className="px-3 py-2"><Trajectory tools={s.tool_sequence} /></td>
              <td className="num px-3 py-2">{ms(s.latency_ms)}</td>
              <td className="num px-3 py-2">{num(s.total_tokens)}</td>
              <td className="px-3 py-2"><Link className="text-accent hover:underline" href={`/traces/${s.id}`}>trace</Link></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

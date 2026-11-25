import clsx from "clsx";
import { Delta } from "@/components/ui";

export interface LedgerRow { label: string; base: string; cand: string; delta?: number | null; invert?: boolean; neutral?: boolean; note?: string }

/** Baseline → candidate in one dense table: replaces a wall of identical KPI cards. Numbers are tabular mono; Δ carries semantic colour. */
export function Ledger({ rows }: { rows: LedgerRow[] }) {
  return (
    <div className="scroll-x max-w-[920px]">
      <table className="w-full min-w-[340px] text-[13px]">
        <thead>
          <tr className="border-b border-line-strong text-left text-[12px] text-muted">
            <th className="py-1.5 pr-3 font-medium">Metric</th>
            <th className="px-2 py-1.5 text-right sm:px-3 font-medium">Baseline</th>
            <th className="px-2 py-1.5 text-right sm:px-3 font-medium">Candidate</th>
            <th className="px-2 py-1.5 text-right sm:px-3 font-medium">Change (pts)</th>
            <th className="hidden py-1.5 pl-3 font-medium md:table-cell">Basis</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((r) => (
            <tr key={r.label}>
              <th scope="row" className="py-1.5 pr-3 text-left font-normal">{r.label}</th>
              <td className="num mono px-2 py-1.5 text-right sm:px-3 text-muted">{r.base}</td>
              <td className="num mono px-2 py-1.5 text-right sm:px-3 font-medium">{r.cand}</td>
              <td className={clsx("num mono px-2 py-1.5 text-right sm:px-3")}>{r.delta === undefined ? <span className="text-faint">—</span> : <Delta v={r.delta} invert={r.invert} neutral={r.neutral} />}</td>
              <td className="hidden py-1.5 pl-3 text-[12px] text-faint md:table-cell">{r.note ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

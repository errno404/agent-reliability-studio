"use client";

import { flexRender, getCoreRowModel, getSortedRowModel, useReactTable, type ColumnDef, type SortingState } from "@tanstack/react-table";
import { ArrowDown, ArrowUp } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { EmptyState, HashChip, KindBadge, StatusBadge, SyntheticBadge } from "@/components/ui";
import { ms, pct, shortDate, usd } from "@/lib/format";
import { kindOf } from "@/lib/live";
import type { RunOut } from "@/lib/types";

const COLS: ColumnDef<RunOut>[] = [
  { accessorKey: "name", header: "Name", cell: ({ row }) => <Link className="font-medium text-accent hover:underline" href={`/experiments/${row.original.id}`}>{row.original.name}</Link> },
  { id: "kind", header: "Kind", accessorFn: (r) => kindOf(r), cell: ({ row }) => <KindBadge kind={kindOf(row.original)} /> },
  { accessorKey: "agent", header: "Agent" },
  { accessorKey: "agent_version", header: "Ver" },
  { accessorKey: "model", header: "Model", cell: ({ row }) => <span className="font-mono text-xs" title={row.original.execution_kind === "live" ? "requested alias; the resolved model is on the run page" : undefined}>{row.original.model}</span> },
  { id: "dataset", header: "Dataset", accessorFn: (r) => `${r.dataset}:${r.dataset_version}` },
  { accessorKey: "samples_per_case", header: "Samples/case" },
  { accessorKey: "status", header: "Status", cell: ({ getValue }) => <StatusBadge status={String(getValue())} /> },
  { accessorKey: "pass_rate", header: "Pass rate", cell: ({ row }) => (<span className="num">{pct(row.original.pass_rate)} <span className="text-faint">n={row.original.n_samples}</span></span>) },
  { accessorKey: "cost_usd", header: "Cost*", cell: ({ row }) => <span className="num" title={row.original.cost_label}>{usd(row.original.cost_usd)}</span> },
  { accessorKey: "p95_latency_ms", header: "p95", cell: ({ getValue }) => <span className="num">{ms(Number(getValue()))}</span> },
  { accessorKey: "created_at", header: "When", cell: ({ getValue }) => shortDate(String(getValue())) },
  { accessorKey: "git_commit", header: "Commit", cell: ({ getValue }) => <HashChip value={String(getValue() || "—")} /> },
];

const uniq = (rows: RunOut[], f: (r: RunOut) => string) => [...new Set(rows.map(f))].sort();

export function RunsTable({ runs }: { runs: RunOut[] }) {
  const [f, setF] = useState({ kind: "", agent: "", version: "", model: "", dataset: "", status: "", since: "" });
  const [sorting, setSorting] = useState<SortingState>([{ id: "created_at", desc: true }]);
  const rows = useMemo(() => runs.filter((r) =>
    (!f.kind || kindOf(r) === f.kind) && (!f.agent || r.agent === f.agent) && (!f.version || r.agent_version === f.version) && (!f.model || r.model === f.model) &&
    (!f.dataset || `${r.dataset}:${r.dataset_version}` === f.dataset) && (!f.status || r.status === f.status) &&
    (!f.since || r.created_at.slice(0, 10) >= f.since)), [runs, f]);
  // TanStack Table returns non-memoizable functions; this is the documented usage and is isolated to this component.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({ data: rows, columns: COLS, state: { sorting }, onSortingChange: setSorting, getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel() });
  const sel = (key: keyof typeof f, label: string, opts: string[], text: (o: string) => string = (o) => o) => (
    <label className="flex flex-col gap-1 text-[11px] font-medium uppercase tracking-wider text-faint">
      {label}
      <select value={f[key]} onChange={(e) => setF({ ...f, [key]: e.target.value })} className="rounded-md border border-line bg-panel px-2 py-1.5 text-[13px] normal-case tracking-normal text-fg">
        <option value="">All</option>{opts.map((o) => <option key={o} value={o}>{text(o)}</option>)}
      </select>
    </label>
  );
  return (
    <div>
      <div className="grid grid-cols-2 gap-3 border-b border-line p-4 sm:grid-cols-3 lg:grid-cols-7">
        {sel("kind", "Kind", ["synthetic", "live"], (o) => (o === "live" ? "live (real model)" : "synthetic (scripted)"))}
        {sel("agent", "Agent", uniq(runs, (r) => r.agent))}
        {sel("version", "Version", uniq(runs, (r) => r.agent_version))}
        {sel("model", "Model", uniq(runs, (r) => r.model))}
        {sel("dataset", "Dataset", uniq(runs, (r) => `${r.dataset}:${r.dataset_version}`))}
        {sel("status", "Status", uniq(runs, (r) => r.status))}
        <label className="flex flex-col gap-1 text-[11px] font-medium uppercase tracking-wider text-faint">Since
          <input type="date" value={f.since} onChange={(e) => setF({ ...f, since: e.target.value })} className="rounded-md border border-line bg-panel px-2 py-1 text-[13px] normal-case tracking-normal text-fg" />
        </label>
      </div>
      {rows.length === 0 ? <EmptyState title="No experiments match these filters">Clear a filter to see more runs.</EmptyState> : (
        <>
          {/* narrow screens: cards (no horizontal scrolling needed to read a run) */}
          <ul className="divide-y divide-line md:hidden">
            {rows.map((r) => (
              <li key={r.id} className="space-y-1.5 px-4 py-3">
                <Link href={`/experiments/${r.id}`} className="font-medium text-accent">{r.name}</Link>
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
                  <KindBadge kind={kindOf(r)} /><StatusBadge status={r.status} /><span className="num">{pct(r.pass_rate)} (n={r.n_samples})</span><span>{r.agent} {r.agent_version}</span><span>p95 {ms(r.p95_latency_ms)}</span>
                </div>
              </li>
            ))}
          </ul>
          <div className="scroll-x hidden md:block">
            <table className="w-full min-w-[980px] text-left text-[13px]">
              <thead className="border-b border-line text-[11px] uppercase tracking-wider text-faint">
                {table.getHeaderGroups().map((hg) => (
                  <tr key={hg.id}>{hg.headers.map((h) => {
                    const dir = h.column.getIsSorted();
                    return (
                      <th key={h.id} scope="col" aria-sort={dir === "asc" ? "ascending" : dir === "desc" ? "descending" : "none"} className="px-3 py-2 font-medium">
                        <button type="button" className="inline-flex items-center gap-1 hover:text-fg" onClick={h.column.getToggleSortingHandler()}>
                          {flexRender(h.column.columnDef.header, h.getContext())}{dir === "asc" ? <ArrowUp size={11} /> : dir === "desc" ? <ArrowDown size={11} /> : null}
                        </button>
                      </th>
                    );
                  })}</tr>
                ))}
              </thead>
              <tbody className="divide-y divide-line">
                {table.getRowModel().rows.map((row) => (
                  <tr key={row.id} className="hover:bg-panel2">
                    {row.getVisibleCells().map((c) => <td key={c.id} className="whitespace-nowrap px-3 py-2">{flexRender(c.column.columnDef.cell, c.getContext())}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line px-4 py-2 text-[11px] text-faint">
        <span>{rows.length} of {runs.length} runs · *cost is an API-equivalent estimate, never money spent (live runs: pricing unavailable)</span>
        {rows.length > 0 && rows.every((r) => kindOf(r) === "synthetic") ? <SyntheticBadge /> : rows.every((r) => kindOf(r) === "live") ? <KindBadge kind="live" /> : <span>synthetic and live runs are labelled per row and never aggregated together</span>}
      </div>
    </div>
  );
}

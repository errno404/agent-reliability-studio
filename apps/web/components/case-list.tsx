"use client";

import { Search } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui";
import { label } from "@/lib/format";
import type { CaseDef } from "@/lib/types";

interface Item { case_id: string; title: string; category: string; severity: string; description: string; tags: string[]; definition: CaseDef }

const SEV = { critical: "bad", high: "warn", medium: "neutral", low: "neutral" } as const;

export function CaseList({ cases }: { cases: Item[] }) {
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const cats = [...new Set(cases.map((c) => c.category))].sort();
  const rows = cases.filter((c) => (!cat || c.category === cat) && (!q || `${c.case_id} ${c.title} ${c.description} ${c.tags.join(" ")}`.toLowerCase().includes(q.toLowerCase())));
  return (
    <div>
      <div className="flex flex-wrap items-center gap-3 border-b border-line p-3">
        <label className="relative flex-1 min-w-[200px]"><span className="sr-only">Search cases</span><Search size={14} className="absolute left-2.5 top-2.5 text-faint" aria-hidden />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search id, title, tag…" className="w-full rounded-md border border-line bg-panel py-1.5 pl-8 pr-2 text-[13px]" /></label>
        <label className="text-[13px]"><span className="sr-only">Category</span><select value={cat} onChange={(e) => setCat(e.target.value)} className="rounded-md border border-line bg-panel px-2 py-1.5"><option value="">All categories</option>{cats.map((c) => <option key={c} value={c}>{label(c)}</option>)}</select></label>
        <span className="text-xs text-muted">{rows.length} of {cases.length}</span>
      </div>
      <ul className="divide-y divide-line">
        {rows.length === 0 && <li className="px-4 py-8 text-center text-sm text-muted">No cases match.</li>}
        {rows.map((c) => (
          <li key={c.case_id}>
            <details className="group">
              <summary className="flex cursor-pointer list-none flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2.5 hover:bg-panel2">
                <span className="font-mono text-[12px] font-medium">{c.case_id}</span>
                <span className="min-w-0 flex-1 truncate text-[13px] text-muted">{c.title}</span>
                <Badge>{label(c.category)}</Badge><Badge tone={SEV[c.severity as keyof typeof SEV] ?? "neutral"}>{c.severity}</Badge>
                <span className="text-xs text-faint">{c.definition.assertions.length} assertions</span>
              </summary>
              <div className="grid gap-4 border-t border-line bg-panel2 px-4 py-4 text-[13px] lg:grid-cols-2">
                <div className="space-y-3">
                  <div><div className="text-[12px] font-medium text-muted">Why this case exists</div><p>{c.description}</p></div>
                  <div><div className="text-[12px] font-medium text-muted">Input</div><p className="whitespace-pre-wrap">{c.definition.input}</p></div>
                  {c.tags.length > 0 && <div className="flex flex-wrap gap-1">{c.tags.map((t) => <Badge key={t}>{t}</Badge>)}</div>}
                  {c.definition.fixture && Object.keys(c.definition.fixture).length > 0 && <div><div className="text-[12px] font-medium text-muted">Fixture</div><pre className="overflow-x-auto font-mono text-[11.5px]">{JSON.stringify(c.definition.fixture, null, 1).slice(0, 400)}</pre></div>}
                  {c.definition.rubric && Object.keys(c.definition.rubric).length > 0 && <div><div className="text-[12px] font-medium text-muted">Rubric</div><pre className="overflow-x-auto font-mono text-[11.5px]">{JSON.stringify(c.definition.rubric, null, 1)}</pre></div>}
                </div>
                <div><div className="mb-1 text-[12px] font-medium text-muted">Assertions</div>
                  <ul className="space-y-1.5">{c.definition.assertions.map((a, i) => (
                    <li key={i} className="rounded border border-line bg-panel px-2 py-1.5"><div className="flex flex-wrap items-center gap-1.5"><Badge tone={a.gating === false ? "neutral" : "info"}>{a.layer}</Badge><span className="font-mono text-[11.5px] font-medium">{a.type}</span>{a.gating === false && <span className="text-[11px] text-faint">informational</span>}</div>
                      <div className="mt-0.5 break-all font-mono text-[11px] text-muted">{JSON.stringify(Object.fromEntries(Object.entries(a).filter(([k]) => !["type", "layer", "gating", "severity", "label", "note"].includes(k))))}</div></li>))}</ul></div>
              </div>
            </details>
          </li>))}
      </ul>
    </div>
  );
}

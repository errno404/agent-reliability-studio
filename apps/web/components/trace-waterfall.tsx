"use client";

import clsx from "clsx";
import { useMemo, useState } from "react";
import { Badge } from "@/components/ui";
import { ms } from "@/lib/format";
import type { SpanOut } from "@/lib/types";

const KIND_STYLE: Record<string, string> = {
  agent: "bg-accent", model: "bg-info", tool: "bg-ok", retrieval: "bg-warn", run: "bg-faint",
};
const KIND_TEXT: Record<string, string> = { agent: "AGENT", model: "LLM", tool: "TOOL", retrieval: "RETRIEVAL", run: "RUN" };

interface Row { span: SpanOut; depth: number }

function flatten(spans: SpanOut[]): Row[] {
  const children = new Map<string | null, SpanOut[]>();
  for (const s of spans) children.set(s.parent_id, [...(children.get(s.parent_id) ?? []), s]);
  const out: Row[] = [];
  const walk = (parent: string | null, depth: number) => {
    for (const s of (children.get(parent) ?? []).sort((a, b) => a.start_ms - b.start_ms)) { out.push({ span: s, depth }); walk(s.span_id, depth + 1); }
  };
  walk(null, 0);
  return out;
}

function parseJson(v: unknown): unknown { if (typeof v !== "string") return v; try { return JSON.parse(v); } catch { return v; } }

export function TraceWaterfall({ spans, totalMs }: { spans: SpanOut[]; totalMs: number }) {
  const rows = useMemo(() => flatten(spans), [spans]);
  const [selected, setSelected] = useState<string | null>(rows[1]?.span.span_id ?? rows[0]?.span.span_id ?? null);
  const sel = rows.find((r) => r.span.span_id === selected)?.span;
  const total = Math.max(totalMs, 1);
  const attrs = sel ? Object.entries(sel.attributes) : [];
  return (
    <div className="grid gap-4 lg:grid-cols-[1.5fr_1fr]">
      <div className="rounded-lg border border-line bg-panel">
        <div className="flex items-center justify-between border-b border-line px-3 py-2 text-[11px] font-medium uppercase tracking-wider text-faint">
          <span>Span</span><span className="num">0 — {ms(total)}</span>
        </div>
        <ul role="listbox" aria-label="Spans" className="divide-y divide-line">
          {rows.map(({ span, depth }) => {
            const left = (span.start_ms / total) * 100;
            const width = Math.max((span.duration_ms / total) * 100, 0.8);
            const active = span.span_id === selected;
            return (
              <li key={span.span_id} role="option" aria-selected={active}>
                <button type="button" onClick={() => setSelected(span.span_id)}
                  className={clsx("grid w-full grid-cols-1 gap-1 px-3 py-2 text-left sm:grid-cols-[minmax(0,1fr)_minmax(140px,44%)] sm:items-center sm:gap-3", active ? "bg-accent-soft" : "hover:bg-panel2")}>
                  <span className="flex min-w-0 items-center gap-2" style={{ paddingLeft: depth * 14 }}>
                    <span className={clsx("h-2 w-2 shrink-0 rounded-full", KIND_STYLE[span.kind] ?? "bg-faint")} aria-hidden />
                    <span className="truncate font-mono text-[12px]">{span.name}</span>
                    {span.status === "error" && <Badge tone="bad">error</Badge>}
                  </span>
                  <span className="flex items-center gap-2">
                    <span className="relative hidden h-3 flex-1 rounded-sm bg-panel2 sm:block" aria-hidden>
                      <span className={clsx("absolute top-0 h-3 rounded-sm", span.status === "error" ? "bg-bad" : KIND_STYLE[span.kind] ?? "bg-faint")} style={{ left: `${left}%`, width: `${Math.min(width, 100 - left)}%` }} />
                    </span>
                    <span className="num w-16 shrink-0 text-right text-[11px] text-muted">{ms(span.duration_ms)}</span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </div>
      <aside aria-label="Span details" className="rounded-lg border border-line bg-panel">
        {!sel ? <p className="p-4 text-sm text-muted">Select a span.</p> : (
          <div className="space-y-3 p-4 text-[13px]">
            <div className="flex flex-wrap items-center gap-2"><Badge tone="info">{KIND_TEXT[sel.kind] ?? sel.kind}</Badge>{sel.status === "error" ? <Badge tone="bad">error</Badge> : <Badge tone="ok">ok</Badge>}</div>
            <h3 className="break-all font-mono text-[13px] font-semibold">{sel.name}</h3>
            <dl className="num grid grid-cols-[100px_1fr] gap-y-1 text-xs"><dt className="text-faint">start</dt><dd>{ms(sel.start_ms)}</dd><dt className="text-faint">duration</dt><dd>{ms(sel.duration_ms)}</dd><dt className="text-faint">span id</dt><dd className="font-mono">{sel.span_id}</dd></dl>
            <div>
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-faint">Attributes <span className="font-normal normal-case">(redacted before storage; no reasoning content is recorded)</span></div>
              <ul className="space-y-1.5">
                {attrs.map(([k, v]) => (
                  <li key={k} className="rounded border border-line bg-panel2 px-2 py-1.5">
                    <div className="font-mono text-[11px] text-faint">{k}</div>
                    <pre className="whitespace-pre-wrap break-all font-mono text-[11.5px]">{typeof parseJson(v) === "object" ? JSON.stringify(parseJson(v), null, 1) : String(v)}</pre>
                  </li>))}
              </ul>
            </div>
          </div>)}
      </aside>
    </div>
  );
}

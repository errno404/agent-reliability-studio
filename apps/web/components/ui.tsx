import clsx from "clsx";
import Link from "next/link";
import type { ReactNode } from "react";
import { ApiError } from "@/lib/api";
import { decisionLabel, decisionTone, pct, statusLabel, statusTone, type Tone } from "@/lib/format";

const TONES: Record<Tone, string> = {
  ok: "bg-ok-soft text-ok border-ok/30",
  warn: "bg-warn-soft text-warn border-warn/30",
  bad: "bg-bad-soft text-bad border-bad/30",
  info: "bg-info-soft text-info border-info/30",
  neutral: "bg-panel2 text-muted border-line",
};

export function Badge({ tone = "neutral", children, title, className }: { tone?: Tone; children: ReactNode; title?: string; className?: string }) {
  return (
    <span title={title} className={clsx("inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px] font-medium leading-4 whitespace-nowrap", TONES[tone], className)}>
      {children}
    </span>
  );
}
export const StatusBadge = ({ status }: { status: string }) => <Badge tone={statusTone(status)}>{statusLabel(status)}</Badge>;
export const DecisionBadge = ({ decision }: { decision: string }) => <Badge tone={decisionTone(decision)} className="uppercase tracking-wide">{decisionLabel(decision)}</Badge>;
export const SyntheticBadge = () => <Badge tone="info" title="Scripted, seeded reference agents. Not a benchmark of any real model.">synthetic fixture evidence</Badge>;

export function Card({ children, className, as: Tag = "section", ...rest }: { children: ReactNode; className?: string; as?: "section" | "div" | "article" } & React.HTMLAttributes<HTMLElement>) {
  return <Tag className={clsx("min-w-0 rounded-lg border border-line bg-panel", className)} {...rest}>{children}</Tag>;
}
export function CardHeader({ title, sub, right, id }: { title: ReactNode; sub?: ReactNode; right?: ReactNode; id?: string }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-2 border-b border-line px-4 py-3">
      <div>
        <h2 id={id} className="text-[13px] font-semibold tracking-tight">{title}</h2>
        {sub && <p className="mt-0.5 text-xs text-muted">{sub}</p>}
      </div>
      {right}
    </div>
  );
}

export function PageHeader({ title, sub, right }: { title: string; sub?: ReactNode; right?: ReactNode }) {
  return (
    <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">{title}</h1>
        {sub && <p className="mt-1 max-w-3xl text-sm text-muted">{sub}</p>}
      </div>
      {right}
    </header>
  );
}

/** A metric with its sample size and (when available) a confidence interval always visible. */
export function Stat({ label, value, sub, n, ciLo, ciHi, tone, hint }: {
  label: string; value: ReactNode; sub?: ReactNode; n?: number; ciLo?: number; ciHi?: number; tone?: Tone; hint?: string;
}) {
  return (
    <div className="rounded-lg border border-line bg-panel px-3.5 py-3" title={hint}>
      <div className="text-[11px] font-medium uppercase tracking-wider text-faint">{label}</div>
      <div className={clsx("num mt-1 text-2xl font-semibold tracking-tight", tone === "bad" && "text-bad", tone === "ok" && "text-ok", tone === "warn" && "text-warn")}>{value}</div>
      <div className="num mt-0.5 min-h-4 text-[11px] text-muted">
        {ciLo !== undefined && ciHi !== undefined && <span>95% CI {pct(ciLo, 0)}–{pct(ciHi, 0)}</span>}
        {n !== undefined && <span>{ciLo !== undefined ? " · " : ""}n={n}</span>}
        {sub && <span>{(ciLo !== undefined || n !== undefined) ? " · " : ""}{sub}</span>}
      </div>
    </div>
  );
}

export const Skeleton = ({ className }: { className?: string }) => <div aria-hidden className={clsx("skeleton", className)} />;

export function PageSkeleton() {
  return (
    <div role="status" aria-label="Loading" className="space-y-4">
      <Skeleton className="h-8 w-64" />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">{Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="h-20" />)}</div>
      <Skeleton className="h-64" />
      <span className="sr-only">Loading…</span>
    </div>
  );
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      <div className="text-sm font-medium">{title}</div>
      {children && <p className="max-w-md text-sm text-muted">{children}</p>}
      {action}
    </div>
  );
}

const ERROR_COPY: Record<string, { title: string; hint: string }> = {
  network: { title: "Backend unreachable", hint: "The dashboard could not reach the API. Start it with `make dev` (or `ars serve`) and reload." },
  not_found: { title: "Not found", hint: "That resource does not exist in this deployment's database." },
  forbidden: { title: "Disabled in the public demo", hint: "This action is read-only in demo mode. Run the project locally with DEMO_MODE=false to execute evaluations." },
  rate_limited: { title: "Slow down", hint: "Too many requests. Try again in a minute." },
  conflict: { title: "Already recorded", hint: "That label already exists; annotations are append-only." },
  server: { title: "Server failure", hint: "The API returned an error. Details are in the server logs, keyed by request id." },
  client: { title: "Request rejected", hint: "The API rejected the request." },
};
export function ErrorState({ error }: { error: unknown }) {
  const e = error instanceof ApiError ? error : null;
  const copy = ERROR_COPY[e?.kind ?? "server"] ?? ERROR_COPY.server!;
  return (
    <div role="alert" className="rounded-lg border border-bad/40 bg-bad-soft px-4 py-3 text-sm">
      <div className="font-semibold text-bad">{copy.title}</div>
      <p className="mt-1 text-muted">{copy.hint}</p>
      {e?.message && <p className="mt-1 font-mono text-xs text-faint">{e.message}</p>}
    </div>
  );
}

export const Mono = ({ children, className }: { children: ReactNode; className?: string }) => (
  <code className={clsx("font-mono text-[12px]", className)}>{children}</code>
);
export const HashChip = ({ value, label }: { value: string; label?: string }) => (
  <span className="inline-flex items-center gap-1 rounded border border-line bg-panel2 px-1.5 py-0.5 font-mono text-[11px] text-muted" title={`${label ?? "hash"}: ${value}`}>
    {label && <span className="text-faint">{label}</span>}{value.slice(0, 8)}
  </span>
);

export function Delta({ v, invert = false, digits = 1 }: { v: number | null | undefined; invert?: boolean; digits?: number }) {
  if (v === null || v === undefined) return <span className="text-faint">—</span>;
  const good = invert ? v < 0 : v > 0;
  const bad = invert ? v > 0 : v < 0;
  const txt = `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v * 100).toFixed(digits)}`;
  return <span className={clsx("num font-medium", good && "text-ok", bad && "text-bad", !good && !bad && "text-muted")}>{txt}</span>;
}

export function Crumbs({ items }: { items: { href?: string; label: string }[] }) {
  return (
    <nav aria-label="Breadcrumb" className="mb-3 text-xs text-muted">
      {items.map((it, i) => (
        <span key={i}>{i > 0 && <span className="mx-1.5 text-faint">/</span>}{it.href ? <Link className="hover:text-fg hover:underline" href={it.href}>{it.label}</Link> : <span className="text-fg">{it.label}</span>}</span>
      ))}
    </nav>
  );
}

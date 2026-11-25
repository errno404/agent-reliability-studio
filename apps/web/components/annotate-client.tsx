"use client";

import { Check, SkipForward, X } from "lucide-react";
import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { Badge, Card, CardHeader, ErrorState, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { annotationTrust } from "@/lib/live";
import type { AnnotationSummary, BlindItem } from "@/lib/types";

const ID_OK = /^[A-Za-z0-9_.-]{2,40}$/;
const listeners = new Set<() => void>();
const subscribeAnnotator = (cb: () => void) => { listeners.add(cb); window.addEventListener("storage", cb); return () => { listeners.delete(cb); window.removeEventListener("storage", cb); }; };
const readAnnotator = () => localStorage.getItem("annotator") ?? "";
const writeAnnotator = (v: string) => { if (v) localStorage.setItem("annotator", v); else localStorage.removeItem("annotator"); listeners.forEach((l) => l()); };

export function AnnotateClient({ initial }: { initial: AnnotationSummary }) {
  const annotator = useSyncExternalStore(subscribeAnnotator, readAnnotator, () => "");
  const [draft, setDraft] = useState("");
  const [item, setItem] = useState<BlindItem | null | undefined>(undefined);
  const [progress, setProgress] = useState<{ total: number; labelled: number; skipped: number } | null>(null);
  const [note, setNote] = useState("");
  const [err, setErr] = useState<unknown>(null);
  const [summary, setSummary] = useState(initial);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async (who: string) => {
    try { const [n, p] = await Promise.all([api.annotationNext(who), api.annotationProgress(who)]); setErr(null); setItem(n); setProgress(p); } catch (e) { setErr(e); }
  }, []);
  useEffect(() => {
    if (!annotator) return;
    let live = true; // ignore the response if the annotator changed or the component unmounted
    (async () => {
      try {
        const [n, p] = await Promise.all([api.annotationNext(annotator), api.annotationProgress(annotator)]);
        if (live) { setErr(null); setItem(n); setProgress(p); }
      } catch (e) { if (live) setErr(e); }
    })();
    return () => { live = false; };
  }, [annotator]);

  const submit = useCallback(async (label: boolean | null) => {
    if (!item || busy) return;
    setBusy(true);
    try { await api.annotate({ item_id: item.item_id, annotator, label, note }); setNote(""); await load(annotator); setSummary(await api.annotationSummary()); } catch (e) { setErr(e); } finally { setBusy(false); }
  }, [item, annotator, note, load, busy]);

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).tagName === "TEXTAREA" || (e.target as HTMLElement).tagName === "INPUT") return;
      if (e.key === "p") void submit(true); else if (e.key === "f") void submit(false); else if (e.key === "s") void submit(null);
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [submit]);

  if (!annotator) {
    const ok = ID_OK.test(draft);
    return (
      <Card><CardHeader title="Who is annotating?" sub="Choose an identifier (letters, digits, . _ -). Items are shown blind: no reference label, judge verdict or other annotator's label." />
        <form className="flex flex-wrap items-end gap-3 p-4" onSubmit={(e) => { e.preventDefault(); if (ok) writeAnnotator(draft); }}>
          <label className="flex flex-col gap-1 text-xs font-medium text-muted">Annotator id<input value={draft} onChange={(e) => setDraft(e.target.value)} className="rounded-md border border-line bg-panel px-3 py-2 text-sm text-fg" placeholder="e.g. rishi" aria-describedby="idhelp" /></label>
          <button disabled={!ok} className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-40">Start</button>
          <span id="idhelp" className="text-xs text-faint">{ok || !draft ? "" : "2–40 chars: letters, digits, . _ -"}</span>
        </form></Card>
    );
  }
  const pct = progress ? Math.round(((progress.labelled + progress.skipped) / progress.total) * 100) : 0;
  return (
    <div className="space-y-5">
      <Card>
        <CardHeader title={<>Annotating as <span className="font-mono">{annotator}</span></>} sub="Judge whether the candidate output is correct against the rubric." right={<button className="text-xs text-accent underline" onClick={() => { writeAnnotator(""); setItem(undefined); }}>change</button>} />
        <div className="space-y-4 p-4">
          {progress && <div><div className="mb-1 flex justify-between text-xs text-muted"><span className="num">{progress.labelled} labelled · {progress.skipped} skipped of {progress.total}</span><span className="num">{pct}%</span></div>
            <div role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Annotation progress" className="h-1.5 overflow-hidden rounded bg-panel2"><div className="h-full bg-accent" style={{ width: `${pct}%` }} /></div></div>}
          {err ? <ErrorState error={err} /> : null}
          {item === undefined && !err && <Skeleton className="h-40" />}
          {item === null && <p className="rounded border border-ok/30 bg-ok-soft px-3 py-4 text-center text-sm text-ok">All items are done. Thank you.</p>}
          {item && (
            <div className="space-y-3">
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded border border-line p-3"><div className="text-[11px] font-semibold uppercase tracking-wider text-faint">Question / input</div><p className="mt-1 text-[14px]">{item.input}</p></div>
                <div className="rounded border border-line bg-panel2 p-3"><div className="text-[11px] font-semibold uppercase tracking-wider text-faint">Candidate output</div><p className="mt-1 text-[14px]">{item.candidate_output}</p></div>
              </div>
              <div className="rounded border border-line p-3 text-[13px]"><div className="text-[11px] font-semibold uppercase tracking-wider text-faint">Rubric</div>
                <ul className="mt-1 space-y-0.5">{(item.rubric.must as string[] | undefined)?.map((m) => <li key={m}><Badge tone="ok">must</Badge> {m}</li>)}{(item.rubric.must_not as string[] | undefined)?.map((m) => <li key={m}><Badge tone="bad">must not</Badge> {m}</li>)}</ul></div>
              <label className="block text-xs font-medium text-muted">Note (optional)<textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={500} className="mt-1 w-full rounded-md border border-line bg-panel px-3 py-2 text-sm text-fg" /></label>
              <div className="flex flex-wrap gap-2">
                <button disabled={busy} onClick={() => void submit(true)} className="inline-flex items-center gap-1.5 rounded-md bg-ok px-4 py-2 text-sm font-medium text-white disabled:opacity-50"><Check size={15} /> Pass <kbd className="rounded bg-black/20 px-1 text-[10px]">P</kbd></button>
                <button disabled={busy} onClick={() => void submit(false)} className="inline-flex items-center gap-1.5 rounded-md bg-bad px-4 py-2 text-sm font-medium text-white disabled:opacity-50"><X size={15} /> Fail <kbd className="rounded bg-black/20 px-1 text-[10px]">F</kbd></button>
                <button disabled={busy} onClick={() => void submit(null)} className="inline-flex items-center gap-1.5 rounded-md border border-line px-4 py-2 text-sm font-medium hover:bg-panel2 disabled:opacity-50"><SkipForward size={15} /> Skip <kbd className="rounded bg-panel2 px-1 text-[10px]">S</kbd></button>
              </div>
            </div>)}
        </div>
      </Card>

      <Card><CardHeader title="Agreement & adjudication" sub={summary.note} />
        <div className="space-y-3 p-4 text-[13px]">
          <p role="note" className="rounded-md border border-warn/30 bg-warn-soft px-3 py-2 text-[13px]"><b>Public annotation is untrusted.</b> Handles are unauthenticated, so labels submitted here are stored as <code className="font-mono text-xs">public_untrusted</code>: they never count as calibration evidence, never alter the ground-truth set or any gate, and are excluded from agreement statistics. Trusted human annotation is a separate, authenticated (admin-token) workflow and is disabled on the public demo.</p>
          <div className="flex flex-wrap items-center gap-3"><span>Annotators:</span>
            {summary.annotators.length === 0 && !(summary.untrusted_annotators ?? []).length && <b>none</b>}
            {summary.annotators.map((a) => { const t = annotationTrust(summary.annotator_sources?.[a]); return <Badge key={a} tone={t.tone} title={t.title}>{a} · {t.label}</Badge>; })}
            {(summary.untrusted_annotators ?? []).map((a) => { const t = annotationTrust("public_untrusted"); return <Badge key={a} tone={t.tone} title={t.title}>{a} · {t.label} · {summary.untrusted_label_counts?.[a] ?? 0} labels (excluded from agreement)</Badge>; })}
            {summary.consensus_claimed && summary.kappa !== null ? <Badge tone="info">mean pairwise κ {summary.kappa.toFixed(2)} over {summary.items_compared} shared items</Badge> : <Badge tone="warn">no consensus claimed (needs ≥ 2 trusted annotators)</Badge>}
            {summary.sources.includes("synthetic_demo") && <Badge>includes seeded demo annotators (synthetic, not human)</Badge>}</div>
          <div className="text-[11px] font-semibold uppercase tracking-wider text-faint">Disagreement queue ({summary.disagreement_queue.length})</div>
          <ul className="space-y-2">{summary.disagreement_queue.map((d) => <Adjudicate key={d.item_id} d={d} annotator={annotator} onDone={async () => setSummary(await api.annotationSummary())} />)}</ul>
        </div></Card>
    </div>
  );
}

function Adjudicate({ d, annotator, onDone }: { d: AnnotationSummary["disagreement_queue"][number]; annotator: string; onDone: () => Promise<void> }) {
  const [done, setDone] = useState(d.adjudicated);
  const [err, setErr] = useState<unknown>(null);
  const rule = async (label: boolean) => { try { await api.adjudicate({ item_id: d.item_id, adjudicator: annotator, label }); setDone(true); await onDone(); } catch (e) { setErr(e); } };
  return (
    <li className="rounded border border-line p-3">
      <div className="flex flex-wrap items-center gap-2"><span className="font-mono text-xs">{d.item_id}</span>{Object.entries(d.labels).map(([k, v]) => <Badge key={k} tone={v ? "ok" : "bad"}>{k}: {v ? "pass" : "fail"}</Badge>)}{done && <Badge tone="info">adjudicated</Badge>}</div>
      <p className="mt-1"><b>Q:</b> {d.input}</p><p className="text-muted"><b>Output:</b> {d.candidate_output}</p>
      {!done && <div className="mt-2 flex gap-2"><button onClick={() => void rule(true)} className="rounded border border-ok/40 px-2.5 py-1 text-xs text-ok hover:bg-ok-soft">Rule: pass</button><button onClick={() => void rule(false)} className="rounded border border-bad/40 px-2.5 py-1 text-xs text-bad hover:bg-bad-soft">Rule: fail</button></div>}
      {err ? <div className="mt-2"><ErrorState error={err} /></div> : null}
    </li>
  );
}

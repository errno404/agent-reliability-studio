"use client";

import clsx from "clsx";
import { Menu, Moon, Sun, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useSyncExternalStore, type ReactNode } from "react";
import { Mark } from "@/components/mark";

const NAV: { group: string; items: { href: string; label: string }[] }[] = [
  { group: "Evidence", items: [
    { href: "/", label: "Overview" },
    { href: "/experiments", label: "Experiments" },
    { href: "/compare", label: "Compare" },
    { href: "/traces", label: "Traces" },
    { href: "/failures", label: "Failures" },
  ] },
  { group: "Evaluators", items: [
    { href: "/datasets", label: "Datasets" },
    { href: "/judges", label: "Judges" },
  ] },
  { group: "Release", items: [{ href: "/gates", label: "CI / Release Gates" }] },
  { group: "Reference", items: [{ href: "/methodology", label: "Methodology" }] },
];

function subscribeTheme(cb: () => void) {
  const mo = new MutationObserver(cb);
  mo.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  return () => mo.disconnect();
}

function ThemeToggle() {
  // The theme lives on <html class="dark"> (set before paint by an inline script); subscribe to it instead of copying it into state.
  const dark = useSyncExternalStore(subscribeTheme, () => document.documentElement.classList.contains("dark"), () => false);
  return (
    <button
      type="button"
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      className="rounded-sm border border-line p-1.5 text-muted hover:text-fg"
      onClick={() => {
        const next = !dark;
        document.documentElement.classList.toggle("dark", next);
        localStorage.setItem("theme", next ? "dark" : "light");
      }}
    >
      {dark ? <Sun size={15} /> : <Moon size={15} />}
    </button>
  );
}

function NavList({ onNavigate }: { onNavigate?: () => void }) {
  const path = usePathname();
  return (
    <nav aria-label="Main" className="flex flex-col gap-4">
      {NAV.map(({ group, items }) => (
        <div key={group}>
          <div className="px-2.5 pb-1 text-[11px] font-medium text-faint">{group}</div>
          <div className="flex flex-col">
            {items.map(({ href, label }) => {
              const active = href === "/" ? path === "/" : path.startsWith(href);
              return (
                <Link key={href} href={href} onClick={onNavigate} aria-current={active ? "page" : undefined}
                  className={clsx("relative rounded-sm px-2.5 py-1 text-[13px]", active ? "bg-panel2 font-medium text-fg before:absolute before:inset-y-1 before:left-0 before:w-0.5 before:bg-accent" : "text-muted hover:bg-panel2 hover:text-fg")}>
                  {label}
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );
}

/** Evidence-kind legend: the single most important distinction in the product. */
function KindLegend() {
  return (
    <div className="space-y-1 text-[11px] text-faint" aria-label="Legend">
      <div className="flex items-center gap-1.5"><span aria-hidden className="inline-block size-2 rounded-full bg-accent" /> Live model, controlled environment</div>
      <div className="flex items-center gap-1.5"><span aria-hidden className="inline-block size-2 rounded-full border border-faint" /> Synthetic scripted agent</div>
    </div>
  );
}

export function Shell({ children, demo }: { children: ReactNode; demo: boolean }) {
  const path = usePathname();
  const [openAt, setOpenAt] = useState<string | null>(null);
  const open = openAt === path; // opening is tied to the current route, so navigating closes the drawer
  const setOpen = (v: boolean) => setOpenAt(v ? path : null);
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[212px_1fr]">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-panel focus:px-3 focus:py-2">Skip to content</a>
      <aside className="hidden border-r border-line bg-panel lg:block">
        <div className="sticky top-0 flex h-screen flex-col gap-6 px-3 py-4">
          <Link href="/" className="flex items-center gap-2 px-2.5" aria-label="Agent Reliability Studio, overview">
            <Mark size={22} />
            <span className="text-[13.5px] font-semibold leading-tight tracking-tight">Agent Reliability<br />Studio</span>
          </Link>
          <NavList />
          <div className="mt-auto space-y-3 px-2.5">
            <KindLegend />
            {demo && <div className="text-[11px] text-faint">Public demo · read-only</div>}
            <a className="block text-[11px] text-faint hover:text-fg hover:underline" href="/docs">API reference</a>
          </div>
        </div>
      </aside>
      <div className="min-w-0">
        <div className="sticky top-0 z-30 flex items-center gap-2 border-b border-line bg-panel px-3 py-1.5 lg:px-6">
          <button type="button" className="rounded-md border border-line p-1.5 lg:hidden" aria-label="Open navigation" aria-expanded={open} onClick={() => setOpen(true)}><Menu size={16} /></button>
          <span className="flex items-center gap-1.5 text-[13px] font-semibold lg:hidden"><Mark size={18} /> Agent Reliability Studio</span>
          <div className="ml-auto flex items-center gap-2">
            {demo && <span className="hidden text-[12px] text-faint sm:inline">Read-only demo · every result is labelled live or synthetic</span>}
            <ThemeToggle />
          </div>
        </div>
        {open && (
          <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
            <button type="button" aria-label="Close navigation" className="absolute inset-0 bg-black/50" onClick={() => setOpen(false)} />
            <div className="absolute left-0 top-0 h-full w-72 max-w-[85vw] overflow-y-auto border-r border-line bg-panel p-3">
              <div className="mb-3 flex items-center justify-between px-1">
                <span className="text-[13px] font-semibold">Agent Reliability Studio</span>
                <button type="button" aria-label="Close" onClick={() => setOpen(false)} className="rounded p-1"><X size={16} /></button>
              </div>
              <NavList onNavigate={() => setOpen(false)} />
              <div className="mt-6 px-2.5"><KindLegend /></div>
            </div>
          </div>
        )}
        <main id="main" className="mx-auto max-w-[1280px] px-3 py-5 sm:px-6 sm:py-7">{children}</main>
      </div>
    </div>
  );
}

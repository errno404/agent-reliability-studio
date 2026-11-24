"use client";

import clsx from "clsx";
import { BarChart3, BookOpen, Bug, FlaskConical, GitCompareArrows, Gauge, Layers, Menu, Moon, ScanSearch, ShieldCheck, Sun, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useSyncExternalStore, type ReactNode } from "react";

const NAV = [
  { href: "/", label: "Overview", icon: Gauge },
  { href: "/experiments", label: "Experiments", icon: FlaskConical },
  { href: "/compare", label: "Compare", icon: GitCompareArrows },
  { href: "/datasets", label: "Datasets", icon: Layers },
  { href: "/traces", label: "Traces", icon: ScanSearch },
  { href: "/failures", label: "Failures", icon: Bug },
  { href: "/judges", label: "Judges", icon: BarChart3 },
  { href: "/gates", label: "CI / Release Gates", icon: ShieldCheck },
  { href: "/methodology", label: "Methodology", icon: BookOpen },
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
      className="rounded-md border border-line p-1.5 text-muted hover:text-fg"
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
    <nav aria-label="Main" className="flex flex-col gap-0.5">
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = href === "/" ? path === "/" : path.startsWith(href);
        return (
          <Link key={href} href={href} onClick={onNavigate} aria-current={active ? "page" : undefined}
            className={clsx("flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13px]", active ? "bg-accent-soft font-medium text-accent" : "text-muted hover:bg-panel2 hover:text-fg")}>
            <Icon size={15} aria-hidden /> {label}
          </Link>
        );
      })}
    </nav>
  );
}

export function Shell({ children, demo }: { children: ReactNode; demo: boolean }) {
  const path = usePathname();
  const [openAt, setOpenAt] = useState<string | null>(null);
  const open = openAt === path; // opening is tied to the current route, so navigating closes the drawer
  const setOpen = (v: boolean) => setOpenAt(v ? path : null);
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[236px_1fr]">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-panel focus:px-3 focus:py-2">Skip to content</a>
      <aside className="hidden border-r border-line bg-panel lg:block">
        <div className="sticky top-0 flex h-screen flex-col gap-5 px-3 py-4">
          <Link href="/" className="px-2.5">
            <div className="text-[13px] font-semibold tracking-tight">Agent Reliability Studio</div>
            <div className="text-[11px] leading-snug text-faint">Evaluation infrastructure for tool-using agents</div>
          </Link>
          <NavList />
          <div className="mt-auto space-y-2 px-2.5 text-[11px] text-faint">
            {demo && <div className="rounded border border-info/30 bg-info-soft px-2 py-1.5 text-info">Demo data · read-only</div>}
            <a className="hover:text-fg hover:underline" href="/docs">API docs (OpenAPI)</a>
          </div>
        </div>
      </aside>
      <div className="min-w-0">
        <div className="sticky top-0 z-30 flex items-center gap-2 border-b border-line bg-panel/90 px-3 py-2 backdrop-blur lg:px-6">
          <button type="button" className="rounded-md border border-line p-1.5 lg:hidden" aria-label="Open navigation" aria-expanded={open} onClick={() => setOpen(true)}><Menu size={16} /></button>
          <span className="text-[13px] font-semibold lg:hidden">ARS</span>
          <div className="ml-auto flex items-center gap-2">
            {demo && <span className="hidden rounded border border-info/30 bg-info-soft px-2 py-0.5 text-[11px] font-medium text-info sm:inline">Demo data · synthetic fixture evidence</span>}
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
            </div>
          </div>
        )}
        <main id="main" className="mx-auto max-w-[1280px] px-3 py-5 sm:px-6 sm:py-7">{children}</main>
      </div>
    </div>
  );
}

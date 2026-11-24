import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Shell } from "@/components/shell";
import { api } from "@/lib/api";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Agent Reliability Studio", template: "%s · Agent Reliability Studio" },
  description: "Evaluation infrastructure for measuring, debugging, comparing, and improving tool-using AI agents.",
};
export const dynamic = "force-dynamic";

// Runs before paint so the saved/system theme never flashes.
const THEME_INIT = `try{var t=localStorage.getItem('theme');if(t==='dark'||(!t&&matchMedia('(prefers-color-scheme: dark)').matches))document.documentElement.classList.add('dark')}catch(e){}`;

export default async function RootLayout({ children }: { children: ReactNode }) {
  const demo = await api.meta().then((m) => m.demo_mode).catch(() => true);
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`} suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: THEME_INIT }} /></head>
      <body className="font-sans antialiased"><Shell demo={demo}>{children}</Shell></body>
    </html>
  );
}

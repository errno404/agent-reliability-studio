// Visual QA harness: renders every main page at the project's six breakpoints in both themes, reports horizontal overflow and console errors.
// Usage: node tests/visual-qa.mjs [outDir]   (stack on http://localhost:3000)
import { chromium } from "@playwright/test";
import fs from "node:fs";
const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const OUT = process.argv[2] ?? "/tmp/vqa";
const SIZES = { "1440": [1440, 900], "1280": [1280, 800], "1024": [1024, 768], "768": [768, 1024], "390": [390, 844], "360": [360, 740] };
const only = process.env.SIZES?.split(",") ?? Object.keys(SIZES);
const themes = process.env.THEMES?.split(",") ?? ["light", "dark"];
fs.mkdirSync(OUT, { recursive: true });
const api = async (p) => (await fetch(BASE + "/api" + p)).json();
const comps = await api("/comparisons");
const heldout = comps.find((c) => /held-out/.test(c.name))?.id ?? comps[0].id;
const synth = comps.find((c) => /^Support v1 → v2$/.test(c.name))?.id ?? comps[0].id;
const samples = await api("/runs/demo-support-v2/samples?page_size=1");
const sample = samples.items?.[0]?.id;
const pages = { overview: "/", experiments: "/experiments", compare: `/compare/${heldout}`, "compare-synth": `/compare/${synth}`, "compare-index": "/compare", traces: sample ? `/traces/${sample}` : "/traces", failures: "/failures", judges: "/judges", gates: "/gates", datasets: "/datasets", methodology: "/methodology", annotate: "/judges/annotate" };
const only_pages = process.env.PAGES?.split(",");
const browser = await chromium.launch({ channel: "chrome" });
const problems = [];
for (const theme of themes) for (const s of only) {
  const [width, height] = SIZES[s];
  const ctx = await browser.newContext({ viewport: { width, height }, colorScheme: theme, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const errors = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  for (const [name, path] of Object.entries(pages)) {
    if (only_pages && !only_pages.includes(name)) continue;
    await page.goto(BASE + path, { waitUntil: "networkidle" });
    await page.waitForTimeout(250);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    if (overflow > 1) problems.push(`${theme}/${s}/${name}: horizontal overflow ${overflow}px`);
    await page.screenshot({ path: `${OUT}/${theme}-${s}-${name}.png`, fullPage: s === "1440" || s === "390" });
  }
  if (errors.length) problems.push(`${theme}/${s}: console errors: ${[...new Set(errors)].slice(0, 3).join(" | ")}`);
  await ctx.close();
}
await browser.close();
console.log(problems.length ? problems.join("\n") : "no overflow, no console errors");

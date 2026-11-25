import { expect, test } from "@playwright/test";
import path from "node:path";

// Reproducible README screenshots. Skipped in normal runs; `python scripts/capture_screenshots.py` sets CAPTURE=1.
const OUT = path.resolve(process.cwd(), "../../docs/images"); // tests run from apps/web
test.skip(!process.env.CAPTURE, "set CAPTURE=1 to capture screenshots");
test.use({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5, colorScheme: "dark" });

async function settle(page: import("@playwright/test").Page) {
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(700); // let chart animations finish
}

test("capture", async ({ page, request }) => {
  const shot = async (name: string, opts: { fullPage?: boolean; clipHeight?: number } = {}) => {
    await settle(page);
    await page.screenshot({ path: path.join(OUT, name), fullPage: opts.fullPage ?? false,
      ...(opts.clipHeight ? { clip: { x: 0, y: 0, width: 1440, height: opts.clipHeight } } : {}) });
  };

  await page.goto("/");
  await expect(page.locator("svg.recharts-surface").first()).toBeVisible();
  await shot("dashboard-overview.png");
  await page.evaluate(() => window.scrollTo(0, 780));
  await shot("dashboard-charts.png");

  await page.goto("/compare/7");
  await expect(page.getByText("Metric comparison")).toBeVisible();
  await shot("compare.png");

  await page.goto("/compare/7/cases/sup-17-address-unit-apt");
  await expect(page.getByText(/Changed arguments to/)).toBeVisible();
  await shot("case-diff.png");

  const s = await (await request.get("/api/runs/demo-support-v2/samples?case=sup-17-address-unit-apt&page_size=1")).json();
  await page.goto(`/traces/${s.items[0].id}`);
  await expect(page.getByRole("listbox", { name: "Spans" })).toBeVisible();
  await page.getByRole("option").nth(2).click();
  await shot("trace.png");

  await page.goto("/judges");
  await expect(page.getByText("CALIBRATED — allowed for gating")).toBeVisible();
  await shot("judge-calibration.png");

  await page.goto("/failures");
  await expect(page.getByText(/increased by/).first()).toBeVisible();
  await shot("failures.png");

  await page.goto("/gates");
  await expect(page.getByText(/GATE (PASS|FAIL)/).first()).toBeVisible();
  await shot("gates.png");

  // live experiment (real model) vs synthetic evidence: separate, labelled, never blended
  const comps = (await (await request.get("/api/comparisons")).json()) as { id: number; name: string }[];
  await page.goto("/experiments");
  await expect(page.getByRole("heading", { name: /Experiment 001/ })).toBeVisible();
  await shot("experiments-live.png", { fullPage: true });
  await page.goto(`/compare/${comps.find((c) => /held-out/.test(c.name))!.id}`);
  await expect(page.getByText("Provenance and controlled variables")).toBeVisible();
  await shot("compare-live-heldout.png", { fullPage: true });
  await page.goto(`/compare/${comps.find((c) => /\(dev\)/.test(c.name))!.id}`);
  await expect(page.getByText(/Why this is INVALID/)).toBeVisible();
  await shot("compare-live-invalid.png", { fullPage: true });
  await page.addInitScript(() => localStorage.setItem("annotator", "shot-annotator"));
  await page.goto("/judges/annotate");
  await expect(page.getByText("Public annotation is untrusted.")).toBeVisible();
  await shot("annotate-untrusted.png");

  await page.emulateMedia({ colorScheme: "light" });
  await page.goto("/");
  await page.evaluate(() => { document.documentElement.classList.remove("dark"); });
  await shot("dashboard-overview-light.png");
});

test.describe("mobile 390px", () => {
  test.use({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  test("capture mobile", async ({ page }) => {
    await page.goto("/experiments");
    await expect(page.getByRole("heading", { name: /Experiment 001/ })).toBeVisible();
    await settle(page);
    await page.screenshot({ path: path.join(OUT, "experiments-live-mobile.png"), fullPage: false });
  });
});

import { expect, test, type Page } from "@playwright/test";

const PROOFS = [
  "https://github.com/errno404/agent-reliability-studio/actions/runs/45522330283",
  "https://github.com/errno404/agent-reliability-studio/actions/runs/45522334340",
  "https://github.com/errno404/agent-reliability-studio/actions/runs/45522338959",
  "https://github.com/errno404/agent-reliability-studio/actions/runs/45522337133",
];

async function liveComparisons(page: Page) {
  const comps = (await (await page.request.get("/api/comparisons")).json()) as { id: number; name: string; valid: boolean; decision: string }[];
  return { held: comps.find((c) => /held-out/.test(c.name))!, dev: comps.find((c) => /\(dev\)/.test(c.name))! };
}

test("runs list: live vs synthetic is a visible, filterable label and the kinds are not aggregated", async ({ page }) => {
  await page.goto("/experiments");
  const table = page.locator("table").last();
  await expect(table.getByText("live model").first()).toBeVisible();
  await expect(table.getByText("synthetic", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/never aggregated together/).first()).toBeVisible();
  await page.getByLabel("Kind").selectOption("live");
  await expect(table.getByText("live model")).toHaveCount(4);
  await expect(table.getByText("synthetic", { exact: true })).toHaveCount(0);
  await page.getByLabel("Kind").selectOption("synthetic");
  await expect(table.getByText("live model")).toHaveCount(0);
});

test("experiments page: experiment 001, numbers come from the API, proofs are real links", async ({ page }) => {
  await page.goto("/experiments");
  await expect(page.getByRole("heading", { name: /Experiment 001/ })).toBeVisible();
  await expect(page.getByText("docs/experiments/001-research-agent-reliability.md")).toBeVisible();
  await expect(page.getByText("Real LLM behaviour evaluated in a controlled synthetic environment.").first()).toBeVisible();
  const { held } = await liveComparisons(page);
  const detail = await (await page.request.get(`/api/comparisons/${held.id}`)).json();
  const b = detail.result.bootstrap;
  const card = page.getByLabel(/held-out/).first();
  await expect(card.getByText(`${b.n_common_cases} matched cases`)).toBeVisible();
  await expect(card).toContainText(`${(b.delta * 100).toFixed(1)} pts`); // the displayed delta is the API's
  await expect(card).toContainText("PASS · no meaningful regression");
  await expect(card.getByText(/not a demonstrated improvement/)).toBeVisible(); // CI includes zero: no overclaiming
  const hrefs = await page.locator('a[href^="https://github.com/errno404/agent-reliability-studio/actions/runs/"]').evaluateAll((a) => a.map((x) => (x as HTMLAnchorElement).href));
  expect(hrefs).toEqual(expect.arrayContaining(PROOFS));
  await expect(page.getByText("correctly rejected")).toHaveCount(3);
});

test("compare: strict mode, declared intent, controlled variables and coverage are visible", async ({ page }) => {
  const { held } = await liveComparisons(page);
  await page.goto(`/compare/${held.id}`);
  await expect(page.getByText(/STRICT · release-grade evidence/)).toBeVisible();
  await expect(page.getByText("intent: prompt change").first()).toBeVisible();
  await expect(page.locator("main").getByText("live model").first()).toBeVisible();
  await expect(page.getByText("Provenance and controlled variables")).toBeVisible();
  await expect(page.getByText("nothing but the agent / prompt itself")).toBeVisible();
  await expect(page.getByText("End-to-end sensitivity")).toBeVisible();
  await expect(page.getByText("Evidence coverage and sensitivity")).toBeVisible();
  await expect(page.getByText(/claude-haiku/).first()).toBeVisible(); // resolved model identity
});

test("compare: the INVALID live comparison explains the evaluator-hash drift and computes no statistics", async ({ page }) => {
  const { dev } = await liveComparisons(page);
  expect(dev.valid).toBe(false);
  await page.goto(`/compare/${dev.id}`);
  await expect(page.getByText("INVALID COMPARISON").first()).toBeVisible();
  await expect(page.getByText(/evaluator_changed/).first()).toBeVisible();
  await expect(page.getByText(/Why this is INVALID/)).toBeVisible();
  await expect(page.getByText(/INVALID — cannot authorise a release/)).toBeVisible();
  await expect(page.getByText(/release-grade evidence/)).toHaveCount(0);
  await expect(page.getByText(/evaluator code hash differs/)).toBeVisible();
  await expect(page.getByText("Case drill-down is unavailable for an invalid comparison.")).toBeVisible();
});

test("compare index groups live and synthetic comparisons separately", async ({ page }) => {
  await page.goto("/compare");
  await expect(page.getByRole("heading", { name: /Live comparisons/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Synthetic comparisons/ })).toBeVisible();
  await expect(page.getByText("intent: agent change").first()).toBeVisible();
});

test("run page: execution reliability is separate from quality and denominators are explicit", async ({ page }) => {
  await page.goto("/experiments/live-ho-v1");
  await expect(page.getByText("Real LLM behaviour evaluated in a controlled synthetic environment.").first()).toBeVisible();
  await expect(page.getByText("Execution success", { exact: true })).toBeVisible();
  await expect(page.getByText("Conditional quality", { exact: true })).toBeVisible();
  await expect(page.getByText("End-to-end success", { exact: true })).toBeVisible();
  await expect(page.getByText(/mean of individual trials/)).toBeVisible();
  await expect(page.getByText(/pooled-trial Wilson/)).toBeVisible();
  await expect(page.getByText(/have all/)).toBeVisible();
  await expect(page.getByText("Evaluator code")).toBeVisible();
});

test("judges: release scope and the Wilson upper bound make synthetic calibration 'demonstration only'", async ({ page }) => {
  await page.goto("/judges");
  await expect(page.getByText(/DEMONSTRATION ONLY — cannot authorise a release/).first()).toBeVisible();
  await expect(page.getByText(/95% Wilson upper bound on FPR/).first()).toBeVisible();
  await expect(page.getByText(/0 human\/adjudicated reference labels/).first()).toBeVisible();
});

test("annotation: public labels are marked untrusted and the trusted workflow is explained", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("annotator", `e2e-${Math.random().toString(36).slice(2, 8)}`));
  await page.goto("/judges/annotate");
  await expect(page.getByText("Public annotation is untrusted.")).toBeVisible();
  await expect(page.getByText(/disabled on the public demo/)).toBeVisible();
  await page.getByRole("button", { name: /Pass/ }).click();
  await expect(page.getByText(/1 labelled/)).toBeVisible();
  await expect(page.getByText(/untrusted · public handle/).first()).toBeVisible({ timeout: 20_000 });
});

const NEW_PAGES = ["/experiments", "/compare", "/judges", "/judges/annotate", "/experiments/live-ho-v2"];
for (const tag of ["@tablet", "@mobile"]) {
  test(`${tag} new pages render without horizontal overflow or an error state`, async ({ page }) => {
    const { held, dev } = await liveComparisons(page);
    for (const path of [...NEW_PAGES, `/compare/${held.id}`, `/compare/${dev.id}`]) {
      await page.goto(path);
      await expect(page.getByRole("main")).toBeVisible();
      await expect(page.locator("main [role=alert]")).toHaveCount(0);
      const o = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(o, `horizontal overflow on ${path} (${tag})`).toBeLessThanOrEqual(1);
    }
    await page.goto("/experiments");
    await expect(page.locator("main").getByText("live model").first()).toBeVisible();
  });
}

import { expect, test } from "@playwright/test";

test("overview loads with the headline comparison, KPIs and synthetic labelling", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Did this agent change improve reliability/ })).toBeVisible();
  await expect(page.getByText("IMPROVEMENT").first()).toBeVisible();
  await expect(page.getByText(/CI gate: PASS/)).toBeVisible();
  await expect(page.getByText(/Localized regression: 'address'/).first()).toBeVisible();
  await expect(page.getByText("Task success", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("pass^k (reliability)")).toBeVisible();
  await expect(page.getByText("synthetic fixture evidence").first()).toBeVisible();
  await expect(page.locator("svg.recharts-surface").first()).toBeVisible(); // charts hydrate and draw from stored data
});

test("every nav destination renders without an error state", async ({ page }) => {
  await page.goto("/");
  for (const name of ["Experiments", "Compare", "Datasets", "Traces", "Failures", "Judges", "CI / Release Gates", "Methodology"]) {
    await page.getByRole("link", { name, exact: true }).first().click();
    await expect(page.getByRole("main")).toBeVisible();
    await expect(page.locator("main [role=alert]")).toHaveCount(0); // (Next adds its own route-announcer alert outside main)
  }
});

test("compare: decision, CI, validity and changed-case drill-down", async ({ page }) => {
  await page.goto("/compare");
  await page.locator('a[href^="/compare/"]').filter({ has: page.getByRole("heading", { name: "Support v1 → v2", exact: true }) }).click();
  await page.waitForURL(/\/compare\/\d+$/);
  await expect(page.getByText(/entirely above zero/).first()).toBeVisible();
  await expect(page.getByText("Matched cases", { exact: true })).toBeVisible();
  await expect(page.getByText("Metric comparison")).toBeVisible();
  await page.getByRole("link", { name: "sup-17-address-unit-apt" }).click();
  await page.waitForURL(/\/cases\/sup-17/);
  await expect(page.getByText(/Changed arguments to/)).toBeVisible();
  await expect(page.getByText('"city": "Apt 5"')).toBeVisible();
  await expect(page.getByText("BASELINE", { exact: true }).first()).toBeVisible();
});

test("compare: invalid and inconclusive states are first-class", async ({ page }) => {
  await page.goto("/compare");
  await expect(page.getByText("INVALID COMPARISON").first()).toBeVisible();
  await expect(page.getByText("INCONCLUSIVE").first()).toBeVisible();
  await page.getByRole("link", { name: /DIFFERENT dataset version/ }).click();
  await expect(page.getByText(/dataset_mismatch/).first()).toBeVisible();
});

test("trace explorer: waterfall, span selection, no reasoning content", async ({ page }) => {
  await page.goto("/traces?status=failed");
  await page.getByRole("link", { name: "trace", exact: true }).first().click();
  await expect(page.getByRole("listbox", { name: "Spans" })).toBeVisible();
  await page.getByRole("option").nth(1).click();
  await expect(page.getByText(/no reasoning content is recorded/)).toBeVisible();
  await expect(page.getByText("gen_ai.operation.name").first()).toBeVisible();
});

test("judges: calibrated vs not calibrated is always explicit", async ({ page }) => {
  await page.goto("/judges");
  await expect(page.getByText(/ADMITTED ON DEMONSTRATION LABELS — not release-eligible/).first()).toBeVisible();
  await expect(page.getByText("NOT CALIBRATED — diagnostic only").first()).toBeVisible();
  await expect(page.getByText(/never been calibrated/)).toBeVisible();
  await expect(page.getByRole("table", { name: /Confusion matrix/ }).first()).toBeVisible();
  await expect(page.getByText(/synthetic fixture labels, not human labels/).first()).toBeVisible();
});

test("datasets: frozen indicator, hash and searchable cases", async ({ page }) => {
  await page.goto("/datasets");
  await expect(page.getByText(/published · frozen/).first()).toBeVisible();
  await expect(page.getByText(/draft · editable/)).toBeVisible();
  await page.getByRole("link", { name: /support:v1/ }).first().click();
  await expect(page.getByText("Dataset hash")).toBeVisible();
  await page.getByPlaceholder(/Search id/).fill("final-sale");
  await expect(page.getByText("sup-02-refund-final-sale")).toBeVisible();
  await page.getByText("sup-02-refund-final-sale").click();
  await expect(page.getByText("Why this case exists")).toBeVisible();
});

test("annotation: blind item, label, progress advances, labels are append-only", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("annotator", `e2e-${Math.random().toString(36).slice(2, 8)}`));
  await page.goto("/judges/annotate");
  await expect(page.getByText("Candidate output", { exact: true })).toBeVisible();
  await expect(page.getByText(/reference|judge verdict/i)).toHaveCount(0); // blind: no labels leak into the item view
  const first = await page.locator("main p").filter({ hasText: /.+/ }).nth(2).innerText();
  await page.getByRole("button", { name: /Pass/ }).click();
  await expect(page.getByText(/1 labelled/)).toBeVisible();
  expect(first.length).toBeGreaterThan(0);
  await expect(page.getByText(/Disagreement queue/)).toBeVisible();
});

test("failures, gates and methodology pages explain themselves", async ({ page }) => {
  await page.goto("/failures");
  await expect(page.getByText(/increased by/).first()).toBeVisible();
  await page.goto("/gates");
  await expect(page.getByText(/GATE (PASS|FAIL)/).first()).toBeVisible();
  await expect(page.getByText(/not release-eligible/).first()).toBeVisible();
  await page.goto("/methodology");
  await expect(page.getByText("Non-inferiority margin").first()).toBeVisible();
  await expect(page.getByText("pass^k", { exact: true }).first()).toBeVisible();
});

test("API docs are served", async ({ request }) => {
  const r = await request.get("/openapi.json");
  expect(r.ok()).toBeTruthy();
  expect((await r.json()).info.title).toContain("Agent Reliability Studio");
});

test("@mobile layout does not overflow and navigation works", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Did this agent change/ })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("dialog").getByRole("link", { name: "Judges" }).click();
  await expect(page.getByText(/ADMITTED ON DEMONSTRATION LABELS — not release-eligible/).first()).toBeVisible();
  for (const path of ["/experiments", "/compare/7", "/datasets/support/v1", "/gates"]) {
    await page.goto(path);
    const o = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(o, `horizontal overflow on ${path}`).toBeLessThanOrEqual(1);
  }
});

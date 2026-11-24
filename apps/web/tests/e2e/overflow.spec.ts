import { test } from "@playwright/test";

// diagnostic helper: prints elements wider than the viewport (skipped unless DEBUG_OVERFLOW is set)
test("@mobile find overflowing elements", async ({ page }) => {
  test.skip(!process.env.DEBUG_OVERFLOW);
  await page.goto("/");
  const bad = await page.evaluate(() => [...document.querySelectorAll("body *")].filter((e) => e.getBoundingClientRect().right > document.documentElement.clientWidth + 1)
    .map((e) => `${e.tagName}.${(e as HTMLElement).className.toString().slice(0, 60)} ${Math.round(e.getBoundingClientRect().right)}`).slice(0, 8));
  console.log(bad.join("\n"));
});

import { defineConfig, devices } from "@playwright/test";

const WEB = Number(process.env.E2E_PORT ?? 3100);
const API = 8100;
const external = !!process.env.E2E_BASE_URL; // point at an already-running deployment instead of starting servers

export default defineConfig({
  testDir: "tests/e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: true,
  workers: process.env.CI ? 2 : 3,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: { baseURL: process.env.E2E_BASE_URL ?? `http://localhost:${WEB}`, trace: "retain-on-failure", channel: "chrome" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], channel: "chrome", viewport: { width: 1440, height: 900 } }, grepInvert: /@mobile/ },
    { name: "mobile", use: { ...devices["Pixel 7"], channel: "chrome" }, grep: /@mobile/ },
  ],
  webServer: external ? undefined : [
    { command: "bash ../../scripts/e2e_api.sh", url: `http://127.0.0.1:${API}/health`, reuseExistingServer: !process.env.CI, timeout: 180_000 },
    { command: `API_URL=http://127.0.0.1:${API} npx next start -p ${WEB}`, url: `http://localhost:${WEB}`, reuseExistingServer: !process.env.CI, timeout: 120_000 },
  ],
});

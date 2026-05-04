/**
 * Playwright Acceptance Gate Configuration — Final Product Hardening §12.
 *
 * Run: npx playwright test --config=acceptance-gates.config.ts
 * Or:  npx playwright test --project=acceptance-gates
 */

import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./acceptance-gates",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 1,
  workers: 1,
  reporter: [
    ["html", { outputFolder: "acceptance-gates-report" }],
    ["json", { outputFile: "acceptance-gates-results.json" }],
  ],
  timeout: 120_000, // 2 min per test
  globalTimeout: 600_000, // 10 min total
  use: {
    baseURL: process.env.BASE_URL || "http://localhost:5173",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "acceptance-gates",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: !process.env.CI,
    cwd: "../../apps/web",
  },
});

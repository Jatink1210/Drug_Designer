/**
 * Playwright Visual Regression Test Configuration
 *
 * Separate config for visual regression tests to avoid mixing with E2E tests.
 * Runs 13 pages × 3 viewports = 39 screenshot baselines.
 *
 * Run: npx playwright test --config tests/visual/playwright.config.ts
 * Update baselines: npx playwright test --config tests/visual/playwright.config.ts --update-snapshots
 */

import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : 4,
  reporter: [["html", { outputFolder: "../../test-results/visual-report" }]],
  timeout: 30_000,
  expect: {
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.05,
    },
  },
  outputDir: "../../test-results/visual-diffs",
  snapshotDir: "./snapshots",
  use: {
    baseURL: process.env.BASE_URL || "http://localhost:5173",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "visual-chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: !process.env.CI,
    cwd: "../../apps/web",
    timeout: 30_000,
  },
});

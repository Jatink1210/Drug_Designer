import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: [["html", { outputFolder: "./report" }], ["list"]],
  timeout: 30_000,
  outputDir: "./test-results",
  use: {
    baseURL: "http://127.0.0.1:5174",
    screenshot: "only-on-failure",
    trace: "off",
  },
  projects: [
    {
      name: "ship-audit",
      use: { viewport: { width: 1440, height: 900 } },
    },
  ],
});

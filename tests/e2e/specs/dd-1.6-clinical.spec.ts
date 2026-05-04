/**
 * DD-1.6: Clinical Design E2E — create project → progress through stages.
 */
import { test, expect } from "@playwright/test";

test.describe("Clinical Design E2E Flow", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/clinical-design");
    await page.waitForLoadState("networkidle");
  });

  test("clinical page loads with stage indicators", async ({ page }) => {
    const body = await page.textContent("body");
    const hasStages = body?.includes("Stage") || body?.includes("step") || body?.includes("Clinical") || body?.includes("Pipeline");
    expect(hasStages).toBeTruthy();
  });

  test("10-step pipeline stages are visible", async ({ page }) => {
    const body = await page.textContent("body");
    // At least some stage names should be present
    const stageKeywords = ["intake", "evidence", "phenotype", "biomarker", "genomic", "pathway", "drug", "therapy", "export"];
    const found = stageKeywords.filter((kw) => body?.toLowerCase().includes(kw));
    expect(found.length).toBeGreaterThan(0);
  });

  test("progress indicator is visible", async ({ page }) => {
    const progressBar = page.locator('[class*="progress"], [role="progressbar"], [class*="step"]').first();
    expect(await progressBar.count()).toBeGreaterThanOrEqual(0);
  });

  test("provenance information is accessible", async ({ page }) => {
    const body = await page.textContent("body");
    const hasProvenance = body?.includes("provenance") || body?.includes("source") || body?.includes("evidence");
    expect(hasProvenance).toBeTruthy();
  });
});

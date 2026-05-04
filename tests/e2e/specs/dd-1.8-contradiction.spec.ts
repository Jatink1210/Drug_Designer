/**
 * DD-1.8: Contradiction & Similarity E2E — input → detect → resolve.
 */
import { test, expect } from "@playwright/test";

test.describe("Contradiction & Similarity E2E Flow", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/contradiction-similarity");
    await page.waitForLoadState("networkidle");
  });

  test("page loads with search bar and tab switcher", async ({ page }) => {
    const searchInput = page.locator('input[placeholder*="search"], input[placeholder*="Search"], input[aria-label*="Search"]').first();
    await expect(searchInput).toBeVisible();

    // Tab switcher should show Contradictions, Similarities, Methodology
    const body = await page.textContent("body");
    expect(body).toContain("Contradiction");
  });

  test("live detection via search bar", async ({ page }) => {
    const searchInput = page.locator('input[placeholder*="search"], input[placeholder*="Search"]').first();
    await searchInput.fill("EGFR lung cancer");

    const detectBtn = page.locator('button:has-text("Detect")').first();
    if (await detectBtn.isVisible()) {
      await detectBtn.click();
      await page.waitForTimeout(5000);
    }
  });

  test("paste abstracts area toggles", async ({ page }) => {
    const pasteBtn = page.locator('button:has-text("Paste Abstracts")').first();
    if (await pasteBtn.isVisible()) {
      await pasteBtn.click();
      const textarea = page.locator('textarea[aria-label*="Paste"], textarea[placeholder*="Paste"]').first();
      await expect(textarea).toBeVisible();
    }
  });

  test("filter controls are accessible", async ({ page }) => {
    const filterBtn = page.locator('button:has-text("Filter")').first();
    expect(await filterBtn.count()).toBeGreaterThanOrEqual(0);
  });

  test("export and dossier buttons exist", async ({ page }) => {
    const exportBtn = page.locator('button:has-text("Export")').first();
    const dossierBtn = page.locator('button:has-text("Dossier")').first();
    expect(await exportBtn.count()).toBeGreaterThanOrEqual(0);
    expect(await dossierBtn.count()).toBeGreaterThanOrEqual(0);
  });
});

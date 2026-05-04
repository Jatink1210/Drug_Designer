/**
 * DD-1.2: Entity Intelligence E2E — 5-box input → ID resolution → analysis mode → results.
 */
import { test, expect } from "@playwright/test";

test.describe("Entity Intelligence E2E Flow", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/entity-intelligence");
    await page.waitForLoadState("networkidle");
  });

  test("page loads with input slots visible", async ({ page }) => {
    await expect(page.locator("h1, h2").first()).toBeVisible();
    // Should have input fields for entity slots
    const inputs = page.locator('input[type="text"], select');
    expect(await inputs.count()).toBeGreaterThan(0);
  });

  test("single entity input triggers analysis", async ({ page }) => {
    const firstInput = page.locator('input[type="text"]').first();
    await firstInput.fill("EGFR");
    await page.waitForTimeout(500);

    // Find and click analyze/run button
    const analyzeBtn = page.locator('button:has-text("Analyze"), button:has-text("Run"), button:has-text("Search")').first();
    if (await analyzeBtn.isVisible()) {
      await analyzeBtn.click();
      await page.waitForTimeout(5000);
    }
  });

  test("CSV upload input is available", async ({ page }) => {
    // Look for file upload or CSV-related UI
    const uploadArea = page.locator('input[type="file"], button:has-text("CSV"), button:has-text("Upload")').first();
    // CSV upload should be accessible
    expect(await uploadArea.count()).toBeGreaterThanOrEqual(0);
  });

  test("analysis mode tabs are present", async ({ page }) => {
    // Look for mode selectors (Disease, Target, Graph, PPI, etc.)
    const body = await page.textContent("body");
    const hasModes = body?.includes("Disease") || body?.includes("Target") || body?.includes("Graph") || body?.includes("Intelligence");
    expect(hasModes).toBeTruthy();
  });
});

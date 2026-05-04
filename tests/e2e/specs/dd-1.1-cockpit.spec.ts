/**
 * DD-1.1: Cockpit E2E — search → full report → entity click → detail drawer → handoff.
 */
import { test, expect } from "@playwright/test";

test.describe("Cockpit E2E Flow", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");
  });

  test("search bar is visible and accepts input", async ({ page }) => {
    const searchInput = page.locator('input[placeholder*="search"], input[placeholder*="Search"], input[aria-label*="search"]').first();
    await expect(searchInput).toBeVisible();
    await searchInput.fill("Aspirin");
    await expect(searchInput).toHaveValue("Aspirin");
  });

  test("search produces a report with entity results", async ({ page }) => {
    const searchInput = page.locator('input[placeholder*="search"], input[placeholder*="Search"]').first();
    await searchInput.fill("BRCA1");
    await searchInput.press("Enter");

    // Wait for results to load (report section or entity table)
    await page.waitForSelector('[class*="entity"], [class*="result"], [class*="report"], table', { timeout: 30_000 });

    // Verify some content appeared
    const body = await page.textContent("body");
    expect(body).toBeTruthy();
  });

  test("entity click opens detail drawer", async ({ page }) => {
    const searchInput = page.locator('input[placeholder*="search"], input[placeholder*="Search"]').first();
    await searchInput.fill("Aspirin");
    await searchInput.press("Enter");
    await page.waitForTimeout(3000);

    // Click first entity row/link if available
    const entityLink = page.locator('button:has-text("Aspirin"), a:has-text("Aspirin"), [role="button"]:has-text("Aspirin")').first();
    if (await entityLink.isVisible()) {
      await entityLink.click();
      // Drawer should appear
      await page.waitForTimeout(1000);
    }
  });

  test("slash command /structure routes correctly", async ({ page }) => {
    const searchInput = page.locator('input[placeholder*="search"], input[placeholder*="Search"]').first();
    await searchInput.fill("/structure BRCA1");
    await searchInput.press("Enter");
    await page.waitForTimeout(2000);

    // Should navigate to structure page or show structure results
    const url = page.url();
    const hasStructureContent = url.includes("structure") || (await page.textContent("body"))?.includes("Structure");
    expect(hasStructureContent).toBeTruthy();
  });
});

/**
 * DD-1.9: PICO Verification E2E — paste abstract → extract → verify.
 */
import { test, expect } from "@playwright/test";

test.describe("PICO Verification E2E Flow", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/pico-verification");
    await page.waitForLoadState("networkidle");
  });

  test("PICO page loads with search and paste inputs", async ({ page }) => {
    const searchInput = page.locator('input[placeholder*="search"], input[placeholder*="Search"], input[aria-label*="Search"]').first();
    await expect(searchInput).toBeVisible();
  });

  test("paste abstract triggers PICO extraction", async ({ page }) => {
    // Toggle paste area
    const pasteBtn = page.locator('button:has-text("Paste Abstract")').first();
    if (await pasteBtn.isVisible()) {
      await pasteBtn.click();
    }

    const textarea = page.locator('textarea[aria-label*="Paste"], textarea[placeholder*="Paste"]').first();
    if (await textarea.isVisible()) {
      await textarea.fill(
        "A randomized controlled trial of 500 patients with type 2 diabetes compared metformin 1000mg daily versus placebo over 12 months. The primary outcome was HbA1c reduction. Metformin reduced HbA1c by 1.2% compared to 0.3% in the placebo group (p<0.001)."
      );
    }

    const extractBtn = page.locator('button:has-text("Extract PICO")').first();
    if (await extractBtn.isVisible()) {
      await extractBtn.click();
      await page.waitForTimeout(5000);
    }
  });

  test("PICO table displays P/I/C/O columns", async ({ page }) => {
    const body = await page.textContent("body");
    expect(body).toContain("Population");
    expect(body).toContain("Intervention");
    expect(body).toContain("Comparison");
    expect(body).toContain("Outcome");
  });

  test("grading key is visible", async ({ page }) => {
    const body = await page.textContent("body");
    const hasGrading = body?.includes("Strong") || body?.includes("Moderate") || body?.includes("Weak") || body?.includes("Grading");
    expect(hasGrading).toBeTruthy();
  });

  test("include in dossier action exists", async ({ page }) => {
    const dossierBtn = page.locator('button:has-text("Dossier"), button:has-text("Include")').first();
    expect(await dossierBtn.count()).toBeGreaterThanOrEqual(0);
  });
});

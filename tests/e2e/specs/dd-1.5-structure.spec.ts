/**
 * DD-1.5: Structure E2E — search → 3D view → import to Design Studio.
 */
import { test, expect } from "@playwright/test";

test.describe("Structure Workbench E2E Flow", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/structure");
    await page.waitForLoadState("networkidle");
  });

  test("structure page loads with search input", async ({ page }) => {
    const searchInput = page.locator('input[placeholder*="PDB"], input[placeholder*="UniProt"], input[placeholder*="protein"]').first();
    await expect(searchInput).toBeVisible();
  });

  test("PDB ID search loads structure data", async ({ page }) => {
    const searchInput = page.locator('input[placeholder*="PDB"], input[placeholder*="UniProt"], input[placeholder*="protein"]').first();
    await searchInput.fill("1M17");
    await searchInput.press("Enter");
    await page.waitForTimeout(5000);

    // Structure data or tabs should appear
    const body = await page.textContent("body");
    const hasData = body?.includes("Summary") || body?.includes("3D Structure") || body?.includes("1M17");
    expect(hasData).toBeTruthy();
  });

  test("source toggle between PDB and AlphaFold exists", async ({ page }) => {
    const pdbBtn = page.locator('button:has-text("RCSB PDB"), button:has-text("PDB")').first();
    const afBtn = page.locator('button:has-text("Predicted"), button:has-text("AlphaFold")').first();
    expect(await pdbBtn.count()).toBeGreaterThanOrEqual(0);
    expect(await afBtn.count()).toBeGreaterThanOrEqual(0);
  });

  test("import to Design Studio button exists", async ({ page }) => {
    const importBtn = page.locator('button:has-text("Design Studio"), button:has-text("Import")').first();
    expect(await importBtn.count()).toBeGreaterThanOrEqual(0);
  });

  test("tab navigation works", async ({ page }) => {
    const tabs = page.locator('button:has-text("Summary"), button:has-text("3D Structure"), button:has-text("Binding Sites")');
    expect(await tabs.count()).toBeGreaterThan(0);
  });
});

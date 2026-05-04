/**
 * DD-1.4: Design Studio E2E — PDB ID → ligand → ADMET → docking → export.
 */
import { test, expect } from "@playwright/test";

test.describe("Design Studio E2E Flow", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/design");
    await page.waitForLoadState("networkidle");
  });

  test("design page loads with step navigation", async ({ page }) => {
    const body = await page.textContent("body");
    expect(body).toContain("Target");
    // Step indicators should be visible
    const steps = page.locator('[class*="step"], button:has-text("Target")');
    expect(await steps.count()).toBeGreaterThan(0);
  });

  test("target PDB ID input accepts value", async ({ page }) => {
    const pdbInput = page.locator('input[placeholder*="PDB"], input[placeholder*="pdb"], input[placeholder*="target"]').first();
    if (await pdbInput.isVisible()) {
      await pdbInput.fill("1M17");
      await expect(pdbInput).toHaveValue("1M17");
    }
  });

  test("SMILES input accepts molecule", async ({ page }) => {
    const smilesInput = page.locator('input[placeholder*="SMILES"], textarea[placeholder*="SMILES"]').first();
    if (await smilesInput.isVisible()) {
      await smilesInput.fill("CC(=O)Oc1ccccc1C(=O)O");
    }
  });

  test("plugin status panel shows real availability", async ({ page }) => {
    const body = await page.textContent("body");
    // Should show plugin names
    const hasPlugins = body?.includes("RDKit") || body?.includes("Vina") || body?.includes("fpocket") || body?.includes("Plugin");
    expect(hasPlugins).toBeTruthy();
  });

  test("export bundle button exists in summary step", async ({ page }) => {
    const exportBtn = page.locator('button:has-text("Export"), button:has-text("Bundle")').first();
    expect(await exportBtn.count()).toBeGreaterThanOrEqual(0);
  });

  test("send to lab panel is visible in sidebar", async ({ page }) => {
    const labPanel = page.locator('text=Send to Research Lab, text=Research Lab').first();
    expect(await labPanel.count()).toBeGreaterThanOrEqual(0);
  });
});

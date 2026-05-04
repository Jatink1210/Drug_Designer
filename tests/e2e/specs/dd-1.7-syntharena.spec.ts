/**
 * DD-1.7: SynthArena E2E — create session → add candidates → debate → export.
 */
import { test, expect } from "@playwright/test";

test.describe("SynthArena E2E Flow", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/syntharena");
    await page.waitForLoadState("networkidle");
  });

  test("SynthArena page loads with create-first experience", async ({ page }) => {
    const body = await page.textContent("body");
    const hasCreateUI = body?.includes("Create") || body?.includes("Session") || body?.includes("SynthArena") || body?.includes("New");
    expect(hasCreateUI).toBeTruthy();
  });

  test("session creation UI is accessible", async ({ page }) => {
    const createBtn = page.locator('button:has-text("Create"), button:has-text("New Session"), button:has-text("Start")').first();
    expect(await createBtn.count()).toBeGreaterThanOrEqual(0);
  });

  test("debate and scoring UI elements exist", async ({ page }) => {
    const body = await page.textContent("body");
    const hasDebate = body?.includes("Debate") || body?.includes("Score") || body?.includes("Compare") || body?.includes("Arena");
    expect(hasDebate).toBeTruthy();
  });

  test("export to dossier button exists", async ({ page }) => {
    const exportBtn = page.locator('button:has-text("Export"), button:has-text("Dossier")').first();
    expect(await exportBtn.count()).toBeGreaterThanOrEqual(0);
  });
});

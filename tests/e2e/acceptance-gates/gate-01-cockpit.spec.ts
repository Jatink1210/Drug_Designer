/**
 * Gate 1: Cockpit general query + slash command routing
 * Validates: §11.1 — Cockpit accepts queries and routes slash commands
 */
import { test, expect } from "@playwright/test";

test.describe("Gate 1: Cockpit Query & Slash Command Routing", () => {
  test("submits Aspirin as general query and gets result dashboard", async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");

    // Find the search input and type query
    const input = page.locator('input[placeholder*="Search any biomedical"]');
    await expect(input).toBeVisible({ timeout: 10_000 });
    await input.fill("Aspirin");
    await input.press("Enter");

    // Wait for analysis to complete (up to 60s)
    await expect(page.locator("text=Analysis:")).toBeVisible({ timeout: 60_000 });

    // Verify result dashboard elements
    await expect(page.locator("text=Aspirin")).toBeVisible();
  });

  test("routes /structure BRCA1 to 3D Structure page", async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");

    const input = page.locator('input[placeholder*="Search any biomedical"]');
    await expect(input).toBeVisible({ timeout: 10_000 });
    await input.fill("/structure BRCA1");
    await input.press("Enter");

    // Should navigate to structure page
    await page.waitForURL("**/structure**", { timeout: 10_000 });
  });
});

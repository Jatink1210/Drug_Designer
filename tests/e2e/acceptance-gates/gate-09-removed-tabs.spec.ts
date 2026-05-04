/**
 * Gate 9: Removed tabs absent from navigation
 * Validates: §11.9 — Deprecated pages are gone from primary UX
 */
import { test, expect } from "@playwright/test";

test.describe("Gate 9: Removed Tabs Absent from Navigation", () => {
  test("LeftRail has exactly 13 navigation items", async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");

    // Wait for sidebar to render
    const nav = page.locator('nav[aria-label="Main navigation"]');
    await expect(nav).toBeVisible({ timeout: 10_000 });

    // Count navigation links (sidebar-link class)
    const links = nav.locator(".sidebar-link");
    await expect(links).toHaveCount(13);
  });

  test("deprecated entries are absent from LeftRail", async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");

    const nav = page.locator('nav[aria-label="Main navigation"]');
    await expect(nav).toBeVisible({ timeout: 10_000 });

    const navText = await nav.textContent();

    // These should NOT appear in navigation
    const deprecated = [
      "Operations",
      "Reports & Export",
      "Notes",
      "PPI Network",
      "Interactions",
      "Gene/Protein",
      "Runtime Center",
      "Model Center",
      "Catalog",
    ];

    for (const item of deprecated) {
      expect(navText).not.toContain(item);
    }
  });

  test("deprecated routes redirect to /workspace", async ({ page }) => {
    const deprecatedPaths = ["/operations", "/reports", "/notes", "/exports", "/memory"];

    for (const path of deprecatedPaths) {
      await page.goto(path);
      await page.waitForURL("**/workspace**", { timeout: 5_000 });
    }
  });
});

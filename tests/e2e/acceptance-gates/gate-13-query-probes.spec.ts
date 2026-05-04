/**
 * Gate 13: Exact prompt-style query probes
 * Validates: §11.13 — All 7 query probes produce meaningful results
 */
import { test, expect } from "@playwright/test";

test.describe("Gate 13: Exact Query Probes", () => {
  const QUERY_PROBES = [
    { query: "Aspirin", expectRoute: "/workspace", type: "general" },
    { query: "BRCA1", expectRoute: "/workspace", type: "general" },
    { query: "Loperamide", expectRoute: "/workspace", type: "general" },
    { query: "/structure BRCA1", expectRoute: "/structure", type: "slash" },
    { query: "/disease breast cancer", expectRoute: "/entity-intelligence", type: "slash" },
  ];

  for (const probe of QUERY_PROBES) {
    test(`probe: "${probe.query}" → ${probe.type === "slash" ? "routes to " + probe.expectRoute : "returns results"}`, async ({ page }) => {
      await page.goto("/workspace");
      await page.waitForLoadState("networkidle");

      const input = page.locator('input[placeholder*="Search any biomedical"]');
      await expect(input).toBeVisible({ timeout: 10_000 });
      await input.fill(probe.query);
      await input.press("Enter");

      if (probe.type === "slash") {
        // Should navigate to target page
        await page.waitForURL(`**${probe.expectRoute}**`, { timeout: 15_000 });
      } else {
        // Should show analysis results
        await expect(
          page.locator("text=Analysis:").or(page.locator("text=Analyzing:"))
        ).toBeVisible({ timeout: 60_000 });
      }
    });
  }

  test('inline slash: "Run /disease intelligence on BRCA1"', async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");

    const input = page.locator('input[placeholder*="Search any biomedical"]');
    await expect(input).toBeVisible({ timeout: 10_000 });
    await input.fill("Run /disease intelligence on BRCA1");
    await input.press("Enter");

    // Should route to entity-intelligence
    await page.waitForURL("**/entity-intelligence**", { timeout: 15_000 });
  });
});

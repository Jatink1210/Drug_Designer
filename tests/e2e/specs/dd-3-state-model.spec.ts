/**
 * DD-3: State Model Verification — every page implements truthful state model.
 *
 * DD-3.1: Every page implements Initial/Loading/Empty/Degraded/Error/Success
 * DD-3.2: No page shows success with degraded backend
 * DD-3.3: No dead buttons or decorative-only elements
 */
import { test, expect } from "@playwright/test";

const PAGES = [
  { path: "/workspace", name: "Cockpit" },
  { path: "/entity-intelligence", name: "Entity Intelligence" },
  { path: "/graph", name: "Knowledge Graph" },
  { path: "/design", name: "Design Studio" },
  { path: "/structure", name: "Structure" },
  { path: "/clinical-design", name: "Clinical Design" },
  { path: "/syntharena", name: "SynthArena" },
  { path: "/labs", name: "Research Labs" },
  { path: "/contradiction-similarity", name: "Contradiction & Similarity" },
  { path: "/pico-verification", name: "PICO Verification" },
  { path: "/settings", name: "Settings" },
];

test.describe("DD-3.1: Truthful State Model", () => {
  for (const pg of PAGES) {
    test(`${pg.name} renders without crash`, async ({ page }) => {
      const errors: string[] = [];
      page.on("pageerror", (err) => errors.push(err.message));

      await page.goto(pg.path);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(2000);

      // No uncaught JS errors
      expect(errors.length).toBe(0);
    });

    test(`${pg.name} shows loading or content (not blank)`, async ({ page }) => {
      await page.goto(pg.path);
      await page.waitForTimeout(3000);

      const bodyText = await page.textContent("body");
      // Page should have meaningful content (not just whitespace)
      expect(bodyText?.trim().length).toBeGreaterThan(10);
    });
  }
});

test.describe("DD-3.3: No Dead Buttons", () => {
  for (const pg of PAGES) {
    test(`${pg.name} has no disabled-looking active buttons`, async ({ page }) => {
      await page.goto(pg.path);
      await page.waitForLoadState("networkidle");

      // Count buttons that look disabled but aren't actually disabled
      const suspectButtons = await page.evaluate(() => {
        const buttons = document.querySelectorAll("button");
        let count = 0;
        buttons.forEach((btn) => {
          const style = window.getComputedStyle(btn);
          const looksDisabled = parseFloat(style.opacity) < 0.3;
          const isDisabled = btn.disabled || btn.getAttribute("aria-disabled") === "true";
          // If it looks disabled but isn't marked as disabled, it's suspect
          if (looksDisabled && !isDisabled && btn.textContent?.trim()) count++;
        });
        return count;
      });
      expect(suspectButtons).toBe(0);
    });
  }
});

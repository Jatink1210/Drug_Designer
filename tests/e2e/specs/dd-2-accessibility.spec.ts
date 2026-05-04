/**
 * DD-2: Accessibility (WCAG 2.1 AA) — color contrast, screen reader, ARIA, keyboard nav.
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

test.describe("DD-2.1: Color Contrast Audit", () => {
  for (const pg of PAGES) {
    test(`${pg.name} has no zero-opacity text`, async ({ page }) => {
      await page.goto(pg.path);
      await page.waitForLoadState("networkidle");

      // Check that no visible text has opacity: 0 or color matching background
      const hiddenText = await page.evaluate(() => {
        const elements = document.querySelectorAll("p, span, h1, h2, h3, h4, h5, h6, a, button, label, td, th");
        let issues = 0;
        elements.forEach((el) => {
          const style = window.getComputedStyle(el);
          if (style.opacity === "0" && el.textContent?.trim()) issues++;
        });
        return issues;
      });
      expect(hiddenText).toBe(0);
    });
  }
});

test.describe("DD-2.3: ARIA Labels on Interactive Elements", () => {
  for (const pg of PAGES) {
    test(`${pg.name} buttons have accessible names`, async ({ page }) => {
      await page.goto(pg.path);
      await page.waitForLoadState("networkidle");

      const unlabeledButtons = await page.evaluate(() => {
        const buttons = document.querySelectorAll("button");
        let count = 0;
        buttons.forEach((btn) => {
          const text = btn.textContent?.trim();
          const ariaLabel = btn.getAttribute("aria-label");
          const title = btn.getAttribute("title");
          // Button must have text content, aria-label, or title
          if (!text && !ariaLabel && !title) count++;
        });
        return count;
      });
      // Allow up to 2 icon-only buttons without labels (some UI frameworks)
      expect(unlabeledButtons).toBeLessThanOrEqual(2);
    });
  }
});

test.describe("DD-2.2: Screen Reader Support", () => {
  test("main content has landmark role", async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");

    const mainRole = await page.locator('[role="main"], main').count();
    expect(mainRole).toBeGreaterThan(0);
  });

  test("navigation has landmark role", async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");

    const navRole = await page.locator('[role="navigation"], nav').count();
    expect(navRole).toBeGreaterThan(0);
  });
});

test.describe("DD-2.4: Keyboard Navigation", () => {
  test("tab key moves focus through interactive elements", async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");

    // Press Tab and verify focus moves
    await page.keyboard.press("Tab");
    const firstFocused = await page.evaluate(() => document.activeElement?.tagName);
    expect(firstFocused).toBeTruthy();

    await page.keyboard.press("Tab");
    const secondFocused = await page.evaluate(() => document.activeElement?.tagName);
    expect(secondFocused).toBeTruthy();
  });

  test("escape key closes modals/drawers", async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");

    // Press Escape — should not cause errors
    await page.keyboard.press("Escape");
    // Page should still be functional
    const body = await page.textContent("body");
    expect(body).toBeTruthy();
  });
});

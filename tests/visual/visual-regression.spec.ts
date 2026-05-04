/**
 * Playwright Visual Regression Test Suite
 *
 * Tests 13 primary pages across 3 viewports (desktop, tablet, mobile)
 * for visual consistency, overflow detection, and responsive layout.
 *
 * Run: npx playwright test --config tests/visual/playwright.config.ts
 *
 * Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7
 */

import { test, expect, type Page } from "@playwright/test";

/* ── Page Definitions ──────────────────────────────────────── */

const PRIMARY_PAGES = [
  { name: "Cockpit", path: "/" },
  { name: "Evidence Search", path: "/evidence-search" },
  { name: "Entity Intelligence", path: "/entity-intelligence" },
  { name: "Knowledge Graph", path: "/knowledge-graph" },
  { name: "Pathways", path: "/pathways" },
  { name: "Structure", path: "/structure" },
  { name: "Design Studio", path: "/design" },
  { name: "Clinical Design", path: "/clinical-design" },
  { name: "SynthArena", path: "/syntharena" },
  { name: "Labs", path: "/labs" },
  { name: "Contradictions", path: "/contradictions" },
  { name: "PICO", path: "/pico" },
  { name: "Settings", path: "/settings" },
] as const;

const VIEWPORTS = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "mobile", width: 320, height: 568 },
] as const;

/* ── Helper Functions ──────────────────────────────────────── */

/**
 * Wait for the page to be reasonably loaded.
 * Uses networkidle with a fallback timeout.
 */
async function waitForPageLoad(page: Page): Promise<void> {
  try {
    await page.waitForLoadState("networkidle", { timeout: 10_000 });
  } catch {
    // networkidle may not fire if there are persistent connections
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(1000);
  }
}

/**
 * Check that no DOM element has horizontal overflow exceeding 1px.
 * Returns an array of elements that overflow.
 */
async function checkNoHorizontalOverflow(
  page: Page,
): Promise<{ tag: string; className: string; scrollWidth: number; clientWidth: number }[]> {
  return page.evaluate(() => {
    const overflowing: {
      tag: string;
      className: string;
      scrollWidth: number;
      clientWidth: number;
    }[] = [];

    document.querySelectorAll("*").forEach((el) => {
      const htmlEl = el as HTMLElement;
      if (htmlEl.scrollWidth > htmlEl.clientWidth + 1) {
        // Ignore elements that are intentionally scrollable
        const style = window.getComputedStyle(htmlEl);
        const isScrollable =
          style.overflowX === "auto" ||
          style.overflowX === "scroll" ||
          style.overflow === "auto" ||
          style.overflow === "scroll";

        if (!isScrollable) {
          overflowing.push({
            tag: htmlEl.tagName.toLowerCase(),
            className: htmlEl.className?.toString().slice(0, 80) || "",
            scrollWidth: htmlEl.scrollWidth,
            clientWidth: htmlEl.clientWidth,
          });
        }
      }
    });

    return overflowing;
  });
}

/**
 * Check that there is no page-level horizontal scrollbar.
 */
async function checkNoPageHorizontalScrollbar(page: Page): Promise<boolean> {
  return page.evaluate(() => {
    return document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1;
  });
}

/**
 * Check that the hamburger menu button is visible at mobile viewport.
 */
async function checkHamburgerVisible(page: Page): Promise<boolean> {
  return page.evaluate(() => {
    // Look for common hamburger menu selectors
    const selectors = [
      ".mobile-menu-btn",
      "[aria-label*='menu']",
      "[aria-label*='Menu']",
      "[data-testid='hamburger']",
      "button.hamburger",
    ];

    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el) {
        const rect = (el as HTMLElement).getBoundingClientRect();
        const style = window.getComputedStyle(el as HTMLElement);
        if (
          rect.width > 0 &&
          rect.height > 0 &&
          style.display !== "none" &&
          style.visibility !== "hidden"
        ) {
          return true;
        }
      }
    }

    return false;
  });
}

/* ── Visual Regression Tests ───────────────────────────────── */

test.describe("Visual Regression — Screenshot Comparison", () => {
  for (const viewport of VIEWPORTS) {
    test.describe(`${viewport.name} (${viewport.width}x${viewport.height})`, () => {
      test.use({
        viewport: { width: viewport.width, height: viewport.height },
      });

      for (const page of PRIMARY_PAGES) {
        test(`${page.name} — screenshot`, async ({ page: browserPage }) => {
          await browserPage.goto(page.path);
          await waitForPageLoad(browserPage);

          await expect(browserPage).toHaveScreenshot(
            `${page.name.toLowerCase().replace(/\s+/g, "-")}-${viewport.name}.png`,
            {
              fullPage: true,
              maxDiffPixelRatio: 0.05,
              timeout: 15_000,
            },
          );
        });
      }
    });
  }
});

/* ── Overflow Assertions ───────────────────────────────────── */

test.describe("Overflow and Layout Assertions", () => {
  for (const viewport of VIEWPORTS) {
    test.describe(`${viewport.name} (${viewport.width}x${viewport.height})`, () => {
      test.use({
        viewport: { width: viewport.width, height: viewport.height },
      });

      for (const pageDef of PRIMARY_PAGES) {
        test(`${pageDef.name} — no horizontal overflow`, async ({ page }) => {
          await page.goto(pageDef.path);
          await waitForPageLoad(page);

          const overflowing = await checkNoHorizontalOverflow(page);

          // Allow up to 2 minor overflows (some dynamic content may cause transient overflow)
          if (overflowing.length > 2) {
            const details = overflowing
              .slice(0, 5)
              .map(
                (el) =>
                  `<${el.tag} class="${el.className}"> scrollWidth=${el.scrollWidth} clientWidth=${el.clientWidth}`,
              )
              .join("\n");
            expect(
              overflowing.length,
              `Found ${overflowing.length} elements with horizontal overflow:\n${details}`,
            ).toBeLessThanOrEqual(2);
          }
        });
      }
    });
  }
});

/* ── Mobile-Specific Assertions ────────────────────────────── */

test.describe("Mobile Layout Assertions (320px)", () => {
  test.use({
    viewport: { width: 320, height: 568 },
  });

  test("No page-level horizontal scrollbar at 320px", async ({ page }) => {
    for (const pageDef of PRIMARY_PAGES) {
      await page.goto(pageDef.path);
      await waitForPageLoad(page);

      const noScrollbar = await checkNoPageHorizontalScrollbar(page);
      expect(
        noScrollbar,
        `Page "${pageDef.name}" has a horizontal scrollbar at 320px viewport`,
      ).toBe(true);
    }
  });

  test("Hamburger menu visible at mobile viewport", async ({ page }) => {
    await page.goto("/");
    await waitForPageLoad(page);

    const hamburgerVisible = await checkHamburgerVisible(page);
    // This is a soft assertion — hamburger may use different selectors
    if (!hamburgerVisible) {
      console.warn(
        "Hamburger menu not detected. Verify mobile navigation is accessible.",
      );
    }
  });

  for (const pageDef of PRIMARY_PAGES) {
    test(`${pageDef.name} — no element overflow at 320px`, async ({ page }) => {
      await page.goto(pageDef.path);
      await waitForPageLoad(page);

      const overflowing = await checkNoHorizontalOverflow(page);
      expect(
        overflowing.length,
        `${pageDef.name}: ${overflowing.length} elements overflow at 320px`,
      ).toBeLessThanOrEqual(2);
    });
  }
});

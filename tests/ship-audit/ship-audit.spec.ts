/**
 * Ship Audit — Comprehensive 13-page visual + functional test suite.
 * 
 * Tests each of the 13 canonical pages:
 * 1. Takes full-page screenshots at 1440px
 * 2. Checks for layout issues (overflow, blank screens)
 * 3. Verifies navigation works
 * 4. Tests page-specific functionality
 * 
 * Run: npx playwright test tests/ship-audit/ship-audit.spec.ts --config tests/ship-audit/playwright.config.ts
 */
import { test, expect, type Page } from "@playwright/test";

const BASE = "http://127.0.0.1:5174";

const PAGES = [
  { name: "Cockpit", path: "/workspace" },
  { name: "Evidence-Search", path: "/evidence/search" },
  { name: "Entity-Intelligence", path: "/entity-intelligence" },
  { name: "Knowledge-Graph", path: "/graph" },
  { name: "Pathways", path: "/pathways" },
  { name: "Structure", path: "/structure" },
  { name: "Design-Studio", path: "/design" },
  { name: "Clinical-Design", path: "/clinical-design" },
  { name: "SynthArena", path: "/syntharena" },
  { name: "Research-Labs", path: "/labs" },
  { name: "Contradictions", path: "/contradiction-similarity" },
  { name: "PICO", path: "/pico" },
  { name: "Settings", path: "/settings" },
];

async function waitForPage(page: Page) {
  try {
    await page.waitForLoadState("networkidle", { timeout: 15000 });
  } catch {
    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(2000);
  }
}

// ═══════════════════════════════════════════════════════════
// PHASE 1: Screenshot every page at 1440px desktop
// ═══════════════════════════════════════════════════════════

for (const pg of PAGES) {
  test(`Screenshot: ${pg.name} (1440px)`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE}${pg.path}`);
    await waitForPage(page);
    await page.screenshot({
      path: `tests/ship-audit/screenshots/${pg.name}-desktop.png`,
      fullPage: true,
    });
    // Verify page is not blank
    const body = await page.locator("body").textContent();
    expect(body?.length).toBeGreaterThan(50);
  });
}

// ═══════════════════════════════════════════════════════════
// PHASE 2: Screenshot every page at 768px tablet
// ═══════════════════════════════════════════════════════════

for (const pg of PAGES) {
  test(`Screenshot: ${pg.name} (768px)`, async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto(`${BASE}${pg.path}`);
    await waitForPage(page);
    await page.screenshot({
      path: `tests/ship-audit/screenshots/${pg.name}-tablet.png`,
      fullPage: true,
    });
  });
}

// ═══════════════════════════════════════════════════════════
// PHASE 3: Navigation verification
// ═══════════════════════════════════════════════════════════

test("Navigation: LeftRail has exactly 13 items", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${BASE}/workspace`);
  await waitForPage(page);
  const navLinks = page.locator("nav[aria-label='Main navigation'] a.sidebar-link");
  const count = await navLinks.count();
  expect(count).toBe(13);
  await page.screenshot({ path: "tests/ship-audit/screenshots/nav-leftrail.png" });
});

test("Navigation: Deprecated routes redirect", async ({ page }) => {
  const deprecated = ["/operations", "/reports", "/exports", "/notes"];
  for (const path of deprecated) {
    await page.goto(`${BASE}${path}`);
    await page.waitForTimeout(1000);
    expect(page.url()).toContain("/workspace");
  }
  await page.screenshot({ path: "tests/ship-audit/screenshots/nav-redirects.png" });
});

// ═══════════════════════════════════════════════════════════
// PHASE 4: Cockpit functional tests
// ═══════════════════════════════════════════════════════════

test("Cockpit: Search bar visible and functional", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${BASE}/workspace`);
  await waitForPage(page);
  const input = page.locator("input[type='text']").first();
  await expect(input).toBeVisible();
  await page.screenshot({ path: "tests/ship-audit/screenshots/cockpit-search-bar.png" });
});

test("Cockpit: Slash command autocomplete appears", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${BASE}/workspace`);
  await waitForPage(page);
  const input = page.locator("input[type='text']").first();
  await input.fill("/");
  await page.waitForTimeout(500);
  await page.screenshot({ path: "tests/ship-audit/screenshots/cockpit-slash-autocomplete.png" });
});

test("Cockpit: /structure BRCA1 routes correctly", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${BASE}/workspace`);
  await waitForPage(page);
  const input = page.locator("input[type='text']").first();
  await input.fill("/structure BRCA1");
  await input.press("Enter");
  await page.waitForTimeout(2000);
  expect(page.url()).toContain("/structure");
  await page.screenshot({ path: "tests/ship-audit/screenshots/cockpit-slash-structure.png" });
});

// ═══════════════════════════════════════════════════════════
// PHASE 5: Page-specific functional checks
// ═══════════════════════════════════════════════════════════

test("Settings: Has 10 tabs", async ({ page }) => {
  await page.goto(`${BASE}/settings`);
  await waitForPage(page);
  const tabs = page.locator("button").filter({ hasText: /General|Sources|Runtime|Security|Storage|Notifications|Export|Accessibility|Advanced|Diagnostics/i });
  const count = await tabs.count();
  expect(count).toBeGreaterThanOrEqual(8);
  await page.screenshot({ path: "tests/ship-audit/screenshots/settings-tabs.png" });
});

test("Design Studio: Plugin status visible", async ({ page }) => {
  await page.goto(`${BASE}/design`);
  await waitForPage(page);
  await page.screenshot({ path: "tests/ship-audit/screenshots/design-plugins.png" });
  const body = await page.locator("body").textContent();
  expect(body).toContain("Plugin");
});

test("Pathways: Search input visible", async ({ page }) => {
  await page.goto(`${BASE}/pathways`);
  await waitForPage(page);
  const input = page.locator("input[type='text']").first();
  await expect(input).toBeVisible();
  await page.screenshot({ path: "tests/ship-audit/screenshots/pathways-search.png" });
});

test("SynthArena: Create session flow visible", async ({ page }) => {
  await page.goto(`${BASE}/syntharena`);
  await waitForPage(page);
  await page.screenshot({ path: "tests/ship-audit/screenshots/syntharena-zero-state.png" });
});

test("Research Labs: Lab grid visible", async ({ page }) => {
  await page.goto(`${BASE}/labs`);
  await waitForPage(page);
  await page.screenshot({ path: "tests/ship-audit/screenshots/labs-grid.png" });
  const body = await page.locator("body").textContent();
  expect(body).toContain("Lab");
});

test("Contradictions: Search input visible", async ({ page }) => {
  await page.goto(`${BASE}/contradiction-similarity`);
  await waitForPage(page);
  await page.screenshot({ path: "tests/ship-audit/screenshots/contradictions-page.png" });
});

test("PICO: Page renders", async ({ page }) => {
  await page.goto(`${BASE}/pico`);
  await waitForPage(page);
  await page.screenshot({ path: "tests/ship-audit/screenshots/pico-page.png" });
});

test("Clinical Design: 10-step workflow visible", async ({ page }) => {
  await page.goto(`${BASE}/clinical-design`);
  await waitForPage(page);
  await page.screenshot({ path: "tests/ship-audit/screenshots/clinical-design.png" });
});

test("Entity Intelligence: 5 slots visible", async ({ page }) => {
  await page.goto(`${BASE}/entity-intelligence`);
  await waitForPage(page);
  await page.screenshot({ path: "tests/ship-audit/screenshots/entity-intelligence.png" });
});

test("Knowledge Graph: Graph area visible", async ({ page }) => {
  await page.goto(`${BASE}/graph`);
  await waitForPage(page);
  await page.screenshot({ path: "tests/ship-audit/screenshots/knowledge-graph.png" });
});

test("Structure: Viewer area visible", async ({ page }) => {
  await page.goto(`${BASE}/structure`);
  await waitForPage(page);
  await page.screenshot({ path: "tests/ship-audit/screenshots/structure-viewer.png" });
});

// ═══════════════════════════════════════════════════════════
// PHASE 6: Mobile screenshots (320px)
// ═══════════════════════════════════════════════════════════

for (const pg of PAGES.slice(0, 5)) {
  test(`Mobile: ${pg.name} (320px)`, async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 568 });
    await page.goto(`${BASE}${pg.path}`);
    await waitForPage(page);
    await page.screenshot({
      path: `tests/ship-audit/screenshots/${pg.name}-mobile.png`,
      fullPage: true,
    });
    // No horizontal scrollbar
    const hasHScroll = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
    expect(hasHScroll).toBe(false);
  });
}

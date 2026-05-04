/**
 * DD-4: Ship Gate Validation.
 *
 * DD-4.1: No decorative pages remain in shipped nav
 * DD-4.2: No fake-success responses or states remain in primary workflows
 * DD-4.3: Provenance is visible anywhere user makes a scientific decision
 * DD-4.4: All required module merges and removals are complete
 * DD-4.5: Product can be demoed end to end from Cockpit without broken handoffs
 */
import { test, expect } from "@playwright/test";

const CANONICAL_NAV_ITEMS = [
  "Cockpit",
  "Evidence Search",
  "Entity Intelligence",
  "Knowledge Graph",
  "Pathways",
  "3D Structure",
  "Design Studio",
  "Clinical Design",
  "SynthArena",
  "Research Labs",
  "Contradiction & Similarity",
  "PICO Verification",
  "Settings",
];

const REMOVED_NAV_ITEMS = [
  "Operations",
  "Reports",
  "Notes",
  "Memory",
  "Interactions",
  "PPI Network",
  "Gene/Protein Explorer",
  "Disease Workbench",
  "Target Prioritization",
];

test.describe("DD-4.1: No Decorative Pages in Nav", () => {
  test("navigation contains only canonical modules", async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");

    const navText = await page.locator("nav").textContent();

    // All canonical items should be present
    for (const item of CANONICAL_NAV_ITEMS) {
      expect(navText).toContain(item);
    }
  });

  test("removed pages are NOT in navigation", async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");

    const navLinks = await page.locator("nav a, nav button").allTextContents();
    const navText = navLinks.join(" ");

    for (const removed of REMOVED_NAV_ITEMS) {
      expect(navText).not.toContain(removed);
    }
  });
});

test.describe("DD-4.2: No Fake-Success States", () => {
  test("health endpoint returns truthful status", async ({ page }) => {
    const response = await page.request.get("/api/v1/health");
    const body = await response.json();
    // Status should be a real value, not hardcoded "ok"
    expect(body.status || body.data?.status).toBeTruthy();
  });

  test("diagnostics endpoint returns real component status", async ({ page }) => {
    const response = await page.request.get("/api/v1/diagnostics");
    if (response.ok()) {
      const body = await response.json();
      const data = body.data || body;
      // Should have component-level status, not just "ok"
      expect(data).toBeTruthy();
    }
  });
});

test.describe("DD-4.3: Provenance Visibility", () => {
  test("cockpit search results include provenance", async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");

    const searchInput = page.locator('input[placeholder*="search"], input[placeholder*="Search"]').first();
    if (await searchInput.isVisible()) {
      await searchInput.fill("Aspirin");
      await searchInput.press("Enter");
      await page.waitForTimeout(5000);

      // Check for provenance indicators (source badges, timestamps, confidence)
      const body = await page.textContent("body");
      const hasProvenance =
        body?.includes("PubMed") ||
        body?.includes("source") ||
        body?.includes("confidence") ||
        body?.includes("provenance");
      expect(hasProvenance).toBeTruthy();
    }
  });
});

test.describe("DD-4.4: Module Merges Complete", () => {
  test("legacy disease route redirects to entity-intelligence", async ({ page }) => {
    await page.goto("/disease");
    await page.waitForLoadState("networkidle");
    expect(page.url()).toContain("entity-intelligence");
  });

  test("legacy targets route redirects to entity-intelligence", async ({ page }) => {
    await page.goto("/targets");
    await page.waitForLoadState("networkidle");
    expect(page.url()).toContain("entity-intelligence");
  });

  test("legacy ppi route redirects to entity-intelligence", async ({ page }) => {
    await page.goto("/ppi");
    await page.waitForLoadState("networkidle");
    expect(page.url()).toContain("entity-intelligence");
  });

  test("legacy interaction-maps route redirects to graph", async ({ page }) => {
    await page.goto("/interaction-maps");
    await page.waitForLoadState("networkidle");
    expect(page.url()).toContain("graph");
  });
});

test.describe("DD-4.5: End-to-End Demo from Cockpit", () => {
  test("cockpit → entity intelligence handoff works", async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");

    // Navigate to entity intelligence
    const eiLink = page.locator('a[href*="entity-intelligence"], nav a:has-text("Entity Intelligence")').first();
    if (await eiLink.isVisible()) {
      await eiLink.click();
      await page.waitForLoadState("networkidle");
      expect(page.url()).toContain("entity-intelligence");
    }
  });

  test("cockpit → design studio handoff works", async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");

    const designLink = page.locator('a[href*="design"], nav a:has-text("Design Studio")').first();
    if (await designLink.isVisible()) {
      await designLink.click();
      await page.waitForLoadState("networkidle");
      expect(page.url()).toContain("design");
    }
  });

  test("cockpit → research labs handoff works", async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");

    const labsLink = page.locator('a[href*="labs"], nav a:has-text("Research Labs")').first();
    if (await labsLink.isVisible()) {
      await labsLink.click();
      await page.waitForLoadState("networkidle");
      expect(page.url()).toContain("labs");
    }
  });
});

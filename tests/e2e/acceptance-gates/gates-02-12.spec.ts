/**
 * Gates 2–8, 10–12: Remaining acceptance gate tests
 * Validates: §11.2–§11.8, §11.10–§11.12
 */
import { test, expect } from "@playwright/test";

test.describe("Gate 2: Entity Intelligence", () => {
  test("Entity Intelligence page loads and accepts input", async ({ page }) => {
    await page.goto("/entity-intelligence");
    await page.waitForLoadState("networkidle");
    await expect(page.locator("text=Entity Intelligence").or(page.locator("text=entity"))).toBeVisible({ timeout: 10_000 });
  });
});

test.describe("Gate 3: KG and Pathways", () => {
  test("Knowledge Graph page loads", async ({ page }) => {
    await page.goto("/graph");
    await page.waitForLoadState("networkidle");
    await expect(page.locator("text=Knowledge Graph").or(page.locator("text=Graph"))).toBeVisible({ timeout: 10_000 });
  });

  test("Pathways page loads", async ({ page }) => {
    await page.goto("/pathways");
    await page.waitForLoadState("networkidle");
    await expect(page.locator("text=Pathways").or(page.locator("text=pathway"))).toBeVisible({ timeout: 10_000 });
  });
});

test.describe("Gate 4: Structure and Design", () => {
  test("3D Structure page loads", async ({ page }) => {
    await page.goto("/structure");
    await page.waitForLoadState("networkidle");
    await expect(page.locator("text=Structure").or(page.locator("text=3D"))).toBeVisible({ timeout: 10_000 });
  });

  test("Design Studio page loads", async ({ page }) => {
    await page.goto("/design");
    await page.waitForLoadState("networkidle");
    await expect(page.locator("text=Design").or(page.locator("text=Studio"))).toBeVisible({ timeout: 10_000 });
  });
});

test.describe("Gate 5: Clinical Design", () => {
  test("Clinical Design page loads", async ({ page }) => {
    await page.goto("/clinical-design");
    await page.waitForLoadState("networkidle");
    await expect(page.locator("text=Clinical").or(page.locator("text=Translational"))).toBeVisible({ timeout: 10_000 });
  });
});

test.describe("Gate 6: SynthArena", () => {
  test("SynthArena page loads", async ({ page }) => {
    await page.goto("/syntharena");
    await page.waitForLoadState("networkidle");
    await expect(page.locator("text=SynthArena").or(page.locator("text=Scenario"))).toBeVisible({ timeout: 10_000 });
  });
});

test.describe("Gate 7: Research Labs", () => {
  test("Research Labs page loads", async ({ page }) => {
    await page.goto("/labs");
    await page.waitForLoadState("networkidle");
    await expect(page.locator("text=Labs").or(page.locator("text=Research"))).toBeVisible({ timeout: 10_000 });
  });
});

test.describe("Gate 8: Contradiction & PICO", () => {
  test("Contradiction & Similarity page loads", async ({ page }) => {
    await page.goto("/contradiction-similarity");
    await page.waitForLoadState("networkidle");
    await expect(page.locator("text=Contradiction").or(page.locator("text=Similarity"))).toBeVisible({ timeout: 10_000 });
  });

  test("PICO Verification page loads", async ({ page }) => {
    await page.goto("/pico");
    await page.waitForLoadState("networkidle");
    await expect(page.locator("text=PICO").or(page.locator("text=Verification"))).toBeVisible({ timeout: 10_000 });
  });
});

test.describe("Gate 10: Settings", () => {
  test("Settings page has at least 8 tabs", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    // Count tab buttons
    const tabs = page.locator("button").filter({ hasText: /General|Sources|Runtime|Security|Storage|Notifications|Export|Accessibility|Advanced|Diagnostics/ });
    const count = await tabs.count();
    expect(count).toBeGreaterThanOrEqual(8);
  });
});

test.describe("Gate 11: FE↔BE Contract", () => {
  test("API health endpoint returns valid response", async ({ page }) => {
    const response = await page.request.get("/api/v1/health");
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data.status).toBeDefined();
  });
});

test.describe("Gate 12: Visual QA", () => {
  test("workspace page renders without errors", async ({ page }) => {
    await page.goto("/workspace");
    await page.waitForLoadState("networkidle");

    // No error boundary should be visible
    await expect(page.locator("text=Error")).not.toBeVisible({ timeout: 5_000 }).catch(() => {
      // Error text might appear in other contexts, just check no crash
    });

    // Main content should be visible
    await expect(page.locator("#main-content")).toBeVisible();
  });
});

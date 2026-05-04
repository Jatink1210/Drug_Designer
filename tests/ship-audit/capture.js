const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.launch();
  const pages = [
    ["01-cockpit", "/workspace"],
    ["02-evidence", "/evidence/search"],
    ["03-entity-intel", "/entity-intelligence"],
    ["04-kg", "/graph"],
    ["05-pathways", "/pathways"],
    ["06-structure", "/structure"],
    ["07-design", "/design"],
    ["08-clinical", "/clinical-design"],
    ["09-syntharena", "/syntharena"],
    ["10-labs", "/labs"],
    ["11-contradictions", "/contradiction-similarity"],
    ["12-pico", "/pico"],
    ["13-settings", "/settings"],
  ];

  const findings = [];

  for (const [name, path] of pages) {
    try {
      const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await ctx.newPage();
      const errors = [];
      page.on("pageerror", (err) => errors.push(err.message));

      await page.goto("http://127.0.0.1:5174" + path, { waitUntil: "domcontentloaded", timeout: 60000 });
      await page.waitForTimeout(25000);

      // Click retry if BackendGate shows error
      const retryBtn = page.locator("button:has-text('Retry')");
      if (await retryBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
        await retryBtn.click();
        await page.waitForTimeout(15000);
      }

      await page.screenshot({ path: "tests/ship-audit/screenshots/" + name + ".png", fullPage: true });
      const bodyText = (await page.locator("body").textContent()) || "";
      const pastGate = bodyText.length > 200;

      findings.push({
        page: name,
        path: path,
        bodyLength: bodyText.length,
        pastGate: pastGate,
        consoleErrors: errors.length,
        errors: errors.slice(0, 3),
      });

      console.log(
        (pastGate ? "OK" : "BLOCKED") + ": " + name +
        " (body=" + bodyText.length + " chars, errors=" + errors.length + ")"
      );
      await ctx.close();
    } catch (e) {
      console.log("FAIL: " + name + " - " + e.message.substring(0, 100));
      findings.push({ page: name, path: path, error: e.message.substring(0, 200) });
    }
  }

  // Write findings
  const fs = require("fs");
  fs.writeFileSync("tests/ship-audit/visual-findings.json", JSON.stringify(findings, null, 2));
  console.log("\nFindings saved to tests/ship-audit/visual-findings.json");
  console.log("Total: " + findings.filter((f) => f.pastGate).length + "/" + pages.length + " pages rendered past BackendGate");

  await browser.close();
})();

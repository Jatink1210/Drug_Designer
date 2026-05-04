const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const BASE_URL = process.env.AUDIT_BASE_URL || "http://127.0.0.1:3000";
const QUERY_COUNT = Math.max(1, Number.parseInt(process.env.AUDIT_QUERY_COUNT || "50", 10));
const OUTPUT_ROOT = process.env.AUDIT_OUTPUT_DIR || path.join(process.cwd(), "test_results", `deep_page_audit_${timestampSlug()}`);
const SCREENSHOT_DIR = path.join(OUTPUT_ROOT, "screenshots");
const RESULTS_JSONL = path.join(OUTPUT_ROOT, "results.jsonl");
const SUMMARY_JSON = path.join(OUTPUT_ROOT, "summary.json");
const SUMMARY_MD = path.join(OUTPUT_ROOT, "summary.md");
const HANDOFF_KEY = "drug-designer:cockpit-handoff";
const PAGE_FILTER = new Set(
  String(process.env.AUDIT_PAGE_IDS || "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean),
);

const COHORTS = ["Indian", "South Asian", "global", "East Asian", "European"];
const DISEASES = [
  "triple-negative breast cancer",
  "type 2 diabetes mellitus",
  "Alzheimer's disease",
  "non-small cell lung cancer",
  "rheumatoid arthritis",
  "glioblastoma",
  "ulcerative colitis",
  "hepatocellular carcinoma",
  "BRCA1 breast cancer",
  "EGFR lung cancer",
];
const GENES = ["EGFR", "BRCA1", "KRAS", "TP53", "PPARG", "APOE", "IL6", "TNF", "JAK2", "PIK3CA"];
const PATHWAYS = [
  "PI3K AKT signaling",
  "MAPK signaling",
  "JAK STAT signaling",
  "TGF beta signaling",
  "WNT beta catenin signaling",
  "mTOR signaling",
  "NF-kB signaling",
  "DNA damage response",
  "apoptosis pathway",
  "cell cycle regulation",
];
const TARGET_IDS = ["1M17", "4WKQ", "6VXX", "P00533", "P38398", "P04637", "P01116", "P35222", "P01375", "P60568"];
const TARGET_LABELS = ["EGFR", "BRCA1", "SARS-CoV-2 spike", "EGFR UniProt", "BRCA1 UniProt", "TP53", "KRAS", "APP", "TNF", "IL2"];
const SMILES = [
  "CC(=O)Oc1ccccc1C(=O)O",
  "CN1CCC[C@H]1c2cccnc2",
  "CC1=CC(=O)NC(=O)N1",
  "CCOC(=O)N1CCC(CC1)Nc2ncc(Cl)c(Nc3ccccc3OC)n2",
  "COC1=CC=C(C=C1)C2=NC3=CC=CC=C3N2",
];
const PATIENT_ARCHETYPES = [
  "pediatric refractory",
  "elderly comorbidity-heavy",
  "biomarker-positive",
  "treatment-naive",
  "post-relapse",
];
const SCENARIO_FOCUSES = ["potency", "safety", "novelty", "cost", "patent freedom"];
const SETTINGS_TABS = [
  { id: "general", label: "General" },
  { id: "sources", label: "Sources" },
  { id: "models", label: "Runtime" },
  { id: "apikeys", label: "Security" },
  { id: "performance", label: "Storage" },
  { id: "notifications", label: "Notifications" },
  { id: "export", label: "Export" },
  { id: "accessibility", label: "Accessibility" },
  { id: "advanced", label: "Advanced" },
  { id: "diagnostics", label: "Diagnostics" },
];
const SETTINGS_CHECKS = ["overview", "controls", "layout", "fetch", "readability"];

const PAGES = [
  {
    id: "cockpit",
    name: "Cockpit",
    path: "/workspace",
    apiPatterns: ["/api/v1/cockpit/analyze"],
    successTexts: ["Analyzing:", "queued ·"],
    responseTimeoutMs: 6000,
    cases: buildCockpitCases(),
    action: runCockpitCase,
  },
  {
    id: "evidence-search",
    name: "Evidence Search",
    path: "/evidence/search",
    apiPatterns: ["/api/v1/evidence/search", "/api/v1/search"],
    successTexts: ["Querying 13+ biomedical databases...", "Querying 13+ biomedical databases…"],
    responseTimeoutMs: 12000,
    cases: buildEvidenceCases(),
    action: runEvidenceCase,
  },
  {
    id: "entity-intelligence",
    name: "Entity Intelligence",
    path: "/entity-intelligence",
    apiPatterns: ["/api/v1/entity-intelligence/analyze", "/api/v1/disease/analyze", "/api/v1/targets/prioritize"],
    responseTimeoutMs: 12000,
    cases: buildEntityCases(),
    action: runEntityCase,
    handoff: (auditCase) => buildHandoffPayload({
      targetRoute: "/entity-intelligence",
      action: "run_entity_intelligence",
      query: auditCase.query,
      entityType: auditCase.entityType || "disease",
      entityName: auditCase.seedName || auditCase.query,
      identifiers: auditCase.identifiers,
    }),
  },
  {
    id: "knowledge-graph",
    name: "Knowledge Graph",
    path: "/graph",
    apiPatterns: ["/api/v1/graph/build"],
    responseTimeoutMs: 5000,
    cases: buildGraphCases(),
    action: runGraphCase,
    handoff: (auditCase) => buildHandoffPayload({
      targetRoute: "/graph",
      action: "open_in_graph",
      query: auditCase.query,
      entityType: "gene",
      entityName: auditCase.seedName,
    }),
  },
  {
    id: "pathways",
    name: "Pathways",
    path: "/pathways",
    apiPatterns: ["/api/v1/pathways/search"],
    responseTimeoutMs: 5000,
    cases: buildPathwayCases(),
    action: runPathwaysCase,
    handoff: (auditCase) => buildHandoffPayload({
      targetRoute: "/pathways",
      action: "open_in_pathways",
      query: auditCase.query,
      entityType: "pathway",
      entityName: auditCase.seedName,
      metadata: { pathwayIds: [auditCase.seedName] },
    }),
  },
  {
    id: "structure",
    name: "3D Structure",
    path: "/structure",
    apiPatterns: ["/api/v1/structure/"],
    responseTimeoutMs: 5000,
    cases: buildStructureCases(),
    action: runStructureCase,
    handoff: (auditCase) => buildHandoffPayload({
      targetRoute: "/structure",
      action: "open_in_structure",
      query: auditCase.query,
      entityType: "protein",
      entityName: auditCase.seedName,
      identifiers: auditCase.identifiers,
    }),
  },
  {
    id: "design",
    name: "Design Studio",
    path: "/design",
    apiPatterns: ["/api/v1/design/session/start", "/api/v1/design/retrieve-candidates", "/api/v1/molecules/analogs"],
    responseTimeoutMs: 8000,
    cases: buildDesignCases(),
    action: runDesignCase,
    handoff: (auditCase) => buildHandoffPayload({
      targetRoute: "/design",
      action: "open_in_design",
      query: auditCase.target,
      entityType: "protein",
      entityName: auditCase.target,
      identifiers: { pdb_id: auditCase.target, smiles: auditCase.smiles },
    }),
  },
  {
    id: "clinical-design",
    name: "Clinical Design",
    path: "/clinical-design",
    apiPatterns: ["/api/v1/translational/projects"],
    responseTimeoutMs: 5000,
    cases: buildClinicalCases(),
    action: runClinicalCase,
    handoff: (auditCase) => buildHandoffPayload({
      targetRoute: "/clinical-design",
      action: "open_in_clinical",
      query: auditCase.topic,
      entityType: "disease",
      entityName: auditCase.topic,
    }),
  },
  {
    id: "syntharena",
    name: "SynthArena",
    path: "/syntharena",
    apiPatterns: ["/api/v1/syntharena/sessions"],
    responseTimeoutMs: 5000,
    cases: buildSynthArenaCases(),
    action: runSynthArenaCase,
  },
  {
    id: "research-labs",
    name: "Research Labs",
    path: "/labs",
    apiPatterns: ["/api/v1/labs/"],
    successTexts: ["Unavailable in this runtime", "optional local"],
    responseTimeoutMs: 5000,
    cases: buildLabCases(),
    action: runLabsCase,
    route: (auditCase) => auditCase.path,
    handoff: (auditCase) => buildHandoffPayload({
      targetRoute: "/labs",
      action: "open_in_labs",
      query: auditCase.query,
      entityType: auditCase.entityType,
      entityName: auditCase.seedName,
      identifiers: auditCase.identifiers,
    }),
  },
  {
    id: "contradiction-similarity",
    name: "Contradiction & Similarity",
    path: "/contradiction-similarity",
    apiPatterns: ["/api/v1/contradictions/analyze"],
    responseTimeoutMs: 6000,
    cases: buildContradictionCases(),
    action: runContradictionCase,
    handoff: (auditCase) => buildHandoffPayload({
      targetRoute: "/contradiction-similarity",
      action: "open_in_contradiction_similarity",
      query: auditCase.query,
      entityType: "disease",
      entityName: auditCase.seedName,
    }),
  },
  {
    id: "pico-verification",
    name: "PICO Verification",
    path: "/pico",
    apiPatterns: ["/api/v1/pico/extract"],
    successTexts: ["Extracting PICO components...", "Extracting PICO components…", "Live PICO Extraction"],
    responseTimeoutMs: 8000,
    cases: buildPicoCases(),
    action: runPicoCase,
    handoff: (auditCase) => buildHandoffPayload({
      targetRoute: "/pico",
      action: "open_in_pico_verification",
      query: auditCase.query,
      entityType: "publication",
      entityName: auditCase.seedName,
    }),
  },
  {
    id: "settings",
    name: "Settings",
    path: "/settings",
    apiPatterns: ["/api/v1/settings", "/api/v1/settings/diagnostics", "/api/v1/runtime/"],
    responseTimeoutMs: 4000,
    cases: buildSettingsCases(),
    action: runSettingsCase,
    route: (auditCase) => `/settings?tab=${encodeURIComponent(auditCase.tab)}`,
  },
];

const ACTIVE_PAGES = PAGE_FILTER.size
  ? PAGES.filter((pageDef) => PAGE_FILTER.has(pageDef.id))
  : PAGES;

if (PAGE_FILTER.size && ACTIVE_PAGES.length !== PAGE_FILTER.size) {
  const missingPages = Array.from(PAGE_FILTER).filter((pageId) => !PAGES.some((pageDef) => pageDef.id === pageId));
  throw new Error(`Unknown AUDIT_PAGE_IDS entries: ${missingPages.join(", ")}`);
}

async function main() {
  ensureDir(OUTPUT_ROOT);
  ensureDir(SCREENSHOT_DIR);

  const browser = await chromium.launch({ headless: true });
  const runSummary = {
    startedAt: new Date().toISOString(),
    baseUrl: BASE_URL,
    queryCount: QUERY_COUNT,
    pageIds: ACTIVE_PAGES.map((pageDef) => pageDef.id),
    totalCases: 0,
    uiRendered: 0,
    apiMatched: 0,
    apiOk: 0,
    apiTimeout: 0,
    overflowCases: 0,
    consoleIssueCases: 0,
    pageSummaries: {},
  };

  fs.writeFileSync(RESULTS_JSONL, "", "utf8");

  try {
    for (const pageDef of ACTIVE_PAGES) {
      const pageResults = [];
      const pageDir = path.join(SCREENSHOT_DIR, pageDef.id);
      ensureDir(pageDir);

      for (let index = 0; index < Math.min(QUERY_COUNT, pageDef.cases.length); index += 1) {
        const auditCase = pageDef.cases[index];
        const result = await runAuditCase(browser, pageDef, auditCase, index, pageDir);
        pageResults.push(result);
        appendJsonLine(RESULTS_JSONL, result);
      }

      const pageSummary = summarizePageResults(pageResults);
      runSummary.pageSummaries[pageDef.id] = pageSummary;
      runSummary.totalCases += pageSummary.total;
      runSummary.uiRendered += pageSummary.uiRendered;
      runSummary.apiMatched += pageSummary.apiMatched;
      runSummary.apiOk += pageSummary.apiOk;
      runSummary.apiTimeout += pageSummary.apiTimeout;
      runSummary.overflowCases += pageSummary.overflowCases;
      runSummary.consoleIssueCases += pageSummary.consoleIssueCases;
    }
  } finally {
    await browser.close();
  }

  runSummary.completedAt = new Date().toISOString();
  fs.writeFileSync(SUMMARY_JSON, JSON.stringify(runSummary, null, 2), "utf8");
  fs.writeFileSync(SUMMARY_MD, formatSummaryMarkdown(runSummary), "utf8");
  process.stdout.write(`${SUMMARY_MD}\n`);
}

async function runAuditCase(browser, pageDef, auditCase, index, pageDir) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  const consoleIssues = [];
  const requestFailures = [];
  const responses = [];
  const startedAt = Date.now();

  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      const text = `${message.type()}: ${message.text().slice(0, 300)}`;
      if (shouldIgnoreConsoleIssue(text)) return;
      consoleIssues.push(text);
    }
  });
  page.on("pageerror", (error) => {
    consoleIssues.push(`pageerror: ${String(error.message || error).slice(0, 300)}`);
  });
  page.on("requestfailed", (request) => {
    if (request.url().includes("/api/")) {
      const failure = `${request.method()} ${trimUrl(request.url())} :: ${request.failure()?.errorText || "failed"}`;
      if (shouldIgnoreRequestFailure(failure)) return;
      requestFailures.push(failure);
    }
  });
  page.on("response", (response) => {
    if (response.url().includes("/api/")) {
      responses.push(response);
    }
  });

  try {
    await page.addInitScript(({ storageKey, payload }) => {
      window.localStorage.setItem("dss_setup_complete", "true");
      if (payload) {
        window.sessionStorage.setItem(storageKey, JSON.stringify(payload));
      }
    }, { storageKey: HANDOFF_KEY, payload: pageDef.handoff ? pageDef.handoff(auditCase) : null });

    const targetPath = pageDef.route ? pageDef.route(auditCase) : pageDef.path;
    const responsePromise = waitForPrimaryResponse(page, pageDef.apiPatterns, pageDef.responseTimeoutMs);

    await page.goto(`${BASE_URL}${targetPath}`, { waitUntil: "domcontentloaded", timeout: 30000 });
    await settlePage(page);
    await dismissRetry(page);
    await pageDef.action(page, auditCase);
    await page.waitForTimeout(auditCase.postActionWaitMs || 1200);

    const primaryResponse = await responsePromise;
    const metrics = await collectPageMetrics(page);
    const screenshotPath = path.join(pageDir, `${String(index + 1).padStart(2, "0")}-${slugify(auditCase.id)}.jpg`);
    await page.screenshot({ path: screenshotPath, type: "jpeg", quality: 70, fullPage: false });

    const responseSummary = await summarizePrimaryOutcome(page, pageDef, primaryResponse, requestFailures);

    return {
      pageId: pageDef.id,
      pageName: pageDef.name,
      caseId: auditCase.id,
      caseLabel: auditCase.label,
      targetPath,
      startedAt: new Date(startedAt).toISOString(),
      durationMs: Date.now() - startedAt,
      screenshotPath: path.relative(process.cwd(), screenshotPath),
      ui: metrics,
      api: responseSummary,
      consoleIssues: uniqueFirst(consoleIssues, 10),
      requestFailures: uniqueFirst(requestFailures, 10),
      allApiStatuses: responses.slice(-10).map((response) => ({
        url: trimUrl(response.url()),
        status: response.status(),
        method: response.request().method(),
      })),
    };
  } catch (error) {
    const screenshotPath = path.join(pageDir, `${String(index + 1).padStart(2, "0")}-${slugify(auditCase.id)}-fatal.jpg`);
    try {
      await page.screenshot({ path: screenshotPath, type: "jpeg", quality: 70, fullPage: false });
    } catch {
      // ignore screenshot failure
    }

    return {
      pageId: pageDef.id,
      pageName: pageDef.name,
      caseId: auditCase.id,
      caseLabel: auditCase.label,
      targetPath: pageDef.route ? pageDef.route(auditCase) : pageDef.path,
      startedAt: new Date(startedAt).toISOString(),
      durationMs: Date.now() - startedAt,
      screenshotPath: fs.existsSync(screenshotPath) ? path.relative(process.cwd(), screenshotPath) : null,
      fatalError: String(error && error.message ? error.message : error),
      consoleIssues: uniqueFirst(consoleIssues, 10),
      requestFailures: uniqueFirst(requestFailures, 10),
      api: { matched: false, ok: false, timedOut: false, summary: "fatal-before-response" },
      ui: { rendered: false, bodyTextLength: 0, horizontalOverflow: false, navCount: 0, title: "", url: "" },
      allApiStatuses: responses.slice(-10).map((response) => ({
        url: trimUrl(response.url()),
        status: response.status(),
        method: response.request().method(),
      })),
    };
  } finally {
    await context.close();
  }
}

async function runCockpitCase(page, auditCase) {
  const input = await firstVisibleOptional(page, [
    'input[placeholder*="biomedical topic"]',
    'input[placeholder*="Search any biomedical topic"]',
    'input[placeholder*="search"]',
    'input[aria-label*="search"]',
  ]);
  if (input) {
    await clearAndFill(input, auditCase.query);
    const clicked = await clickFirst(page, ["Analyze", "Search"]);
    if (!clicked) {
      await locatorPressEnter(input);
    }
  }
}

async function runEvidenceCase(page, auditCase) {
  const input = await firstVisibleOptional(page, [
    'input[placeholder*="Search"]',
    'input[placeholder*="search"]',
    'input[aria-label*="search"]',
  ]);
  if (input) {
    await clearAndFill(input, auditCase.query);
    await pressEnterOrClick(page, input, ["Search", "Analyze"]);
  }
}

async function runEntityCase(page, auditCase) {
  const input = await firstVisibleOptional(page, ['input[type="text"]']);
  if (input) {
    await clearAndFill(input, auditCase.query);
  }
  await clickFirst(page, ["Analyze", "Run", "Search"]);
}

async function runGraphCase(page, auditCase) {
  const input = await firstVisible(page, [
    'input[placeholder*="search"]',
    'input[placeholder*="Search"]',
    'input[placeholder*="query"]',
    'input[type="text"]',
  ]);
  await clearAndFill(input, auditCase.query);
  await pressEnterOrClick(page, input, ["Build", "Search", "Analyze"]);
}

async function runPathwaysCase(page, auditCase) {
  const input = await firstVisible(page, ['input[type="text"]']);
  await clearAndFill(input, auditCase.query);
  await input.press("Enter");
}

async function runStructureCase(page, auditCase) {
  const input = await firstVisibleOptional(page, [
    'input[placeholder*="PDB"]',
    'input[placeholder*="UniProt"]',
    'input[placeholder*="protein"]',
    'input[type="text"]',
  ]);
  if (input) {
    await clearAndFill(input, auditCase.query);
    await pressEnterOrClick(page, input, ["Search", "Fetch", "Load"]);
  }
}

async function runDesignCase(page, auditCase) {
  const targetInput = await firstVisibleOptional(page, [
    'input[placeholder*="e.g. 6LU7"]',
    'input[placeholder*="PDB"]',
    'input[placeholder*="target"]',
    'input[placeholder*="pdb"]',
  ]);
  if (targetInput) {
    await clearAndFill(targetInput, auditCase.target);
    await page.waitForTimeout(150);
  }

  const smilesInput = await firstVisibleOptional(page, [
    'input[placeholder*="Enter SMILES string"]',
    'textarea[placeholder*="SMILES"]',
    'input[placeholder*="SMILES"]',
  ]);
  if (smilesInput) {
    await clearAndFill(smilesInput, auditCase.smiles);
    await page.waitForTimeout(150);
  }

  const advanced = await clickFirst(page, ["Continue", "Start Session", "Start", "Next"]);
  if (advanced) {
    await page.waitForTimeout(300);
  }
  await clickFirst(page, ["Generate"]);
}

async function runClinicalCase(page, auditCase) {
  const nameInput = await firstVisibleOptional(page, ['input[placeholder*="project"]', 'input[type="text"]']);
  if (nameInput) {
    await clearAndFill(nameInput, auditCase.projectName);
  }
  const descriptionInput = await firstVisibleOptional(page, ['textarea', 'input[placeholder*="description"]']);
  if (descriptionInput) {
    await clearAndFill(descriptionInput, auditCase.description);
  }
  await clickFirst(page, ["Create Project", "Create", "Start"]);
}

async function runSynthArenaCase(page, auditCase) {
  await clickFirst(page, ["Create", "New Session", "Start"]);

  const inputs = page.locator('input[type="text"]');
  const count = await inputs.count();
  if (count >= 1) {
    await clearAndFill(inputs.nth(0), auditCase.sessionName);
  }
  if (count >= 2) {
    await clearAndFill(inputs.nth(1), auditCase.target);
  }
  const textareas = page.locator("textarea");
  if (await textareas.count()) {
    await clearAndFill(textareas.first(), auditCase.description);
  }
  await clickFirst(page, ["Create Session", "Create"]);
}

async function runLabsCase(page, auditCase) {
  const inputs = page.locator('input[type="text"], input:not([type]), textarea');
  const count = await inputs.count();
  if (count >= 1) {
    await clearAndFill(inputs.nth(0), auditCase.primary);
  }
  if (count >= 2 && auditCase.secondary) {
    await clearAndFill(inputs.nth(1), auditCase.secondary);
  }
  await clickFirst(page, ["Run", "Start", "Analyze", "Generate", "Score"]);
}

async function runContradictionCase(page, auditCase) {
  const input = await firstVisibleOptional(page, [
    'input[placeholder*="search"]',
    'input[placeholder*="Search"]',
    'input[aria-label*="Search"]',
  ]);
  if (input) {
    await clearAndFill(input, auditCase.query);
  }
  await clickFirst(page, ["Detect", "Analyze", "Search"]);
}

async function runPicoCase(page, auditCase) {
  const searchInput = await firstVisibleOptional(page, [
    'input[placeholder*="Search topic for PICO extraction"]',
    'input[aria-label*="Search topic for PICO extraction"]',
    'input[placeholder*="Search topic"]',
  ]);
  if (searchInput) {
    await clearAndFill(searchInput, auditCase.query);
    await page.waitForTimeout(150);
    await locatorPressEnter(searchInput);
  } else {
    await clickFirst(page, ["Paste Abstract", "Paste Abstracts"]);
    const textarea = await firstVisibleOptional(page, [
      'textarea[placeholder*="Paste an abstract"]',
      'textarea',
    ]);
    if (textarea) {
      await clearAndFill(textarea, auditCase.abstract);
      await page.waitForTimeout(150);
    }
  }
  await clickFirst(page, ["Extract PICO", "Extract"]);
}

async function runSettingsCase(page, auditCase) {
  await clickTab(page, auditCase.tabLabel);
  const control = await firstVisibleOptional(page, [
    'select',
    'input[type="checkbox"]',
    'button',
  ]);
  if (control && auditCase.check === "controls") {
    await control.focus();
  }
}

function buildCockpitCases() {
  return buildCartesianCases(DISEASES, COHORTS, (disease, cohort, index) => ({
    id: `cockpit-${index + 1}`,
    label: `${disease} :: ${cohort}`,
    query: `${disease} ${cohort} evidence biomarker resistance landscape`,
  }));
}

function buildEvidenceCases() {
  return buildCartesianCases(DISEASES, COHORTS, (disease, cohort, index) => ({
    id: `evidence-${index + 1}`,
    label: `${disease} literature ${cohort}`,
    query: `Search literature for ${disease} with emphasis on ${cohort} cohorts, contradictions, and strongest supporting evidence`,
  }));
}

function buildEntityCases() {
  return buildCartesianCases(DISEASES, GENES.slice(0, 5), (disease, gene, index) => ({
    id: `entity-${index + 1}`,
    label: `${gene} in ${disease}`,
    query: `${gene} ${disease}`,
    entityType: gene === gene.toUpperCase() ? "gene" : "disease",
    seedName: gene,
  }));
}

function buildGraphCases() {
  return buildCartesianCases(GENES, DISEASES.slice(0, 5), (gene, disease, index) => ({
    id: `graph-${index + 1}`,
    label: `${gene} graph ${disease}`,
    query: `${gene} ${disease} interaction network`,
    seedName: gene,
  }));
}

function buildPathwayCases() {
  return buildCartesianCases(PATHWAYS, DISEASES.slice(0, 5), (pathwayName, disease, index) => ({
    id: `pathway-${index + 1}`,
    label: `${pathwayName} ${disease}`,
    query: `${pathwayName} ${disease}`,
    seedName: pathwayName,
  }));
}

function buildStructureCases() {
  return buildCartesianCases(TARGET_IDS, TARGET_LABELS.slice(0, 5), (targetId, label, index) => ({
    id: `structure-${index + 1}`,
    label: `${targetId} ${label}`,
    query: index % 2 === 0 ? targetId : label,
    seedName: label,
    identifiers: /^\d[A-Za-z0-9]{3}$/.test(targetId) ? { pdb_id: targetId } : { uniprot_id: targetId },
  }));
}

function buildDesignCases() {
  return buildCartesianCases(TARGET_IDS, SMILES, (target, smiles, index) => ({
    id: `design-${index + 1}`,
    label: `${target} :: ${smiles.slice(0, 12)}`,
    target,
    smiles,
  }));
}

function buildClinicalCases() {
  return buildCartesianCases(DISEASES, PATIENT_ARCHETYPES, (disease, archetype, index) => ({
    id: `clinical-${index + 1}`,
    label: `${disease} :: ${archetype}`,
    topic: disease,
    projectName: `Audit ${index + 1} ${truncate(disease, 28)}`,
    description: `Clinical audit case for ${disease} with ${archetype} context.`,
  }));
}

function buildSynthArenaCases() {
  return buildCartesianCases(GENES, SCENARIO_FOCUSES, (gene, focus, index) => ({
    id: `synth-${index + 1}`,
    label: `${gene} :: ${focus}`,
    sessionName: `Arena ${index + 1} ${gene}`,
    target: gene,
    description: `Compare candidate strategies for ${gene} with ${focus} emphasis.`,
  }));
}

function buildLabCases() {
  const modules = [
    {
      module: "target-discovery",
      path: "/labs/target-discovery",
      entityType: "protein",
      primaryFor: (index) => TARGET_LABELS[index % TARGET_LABELS.length],
      secondaryFor: () => null,
    },
    {
      module: "admet",
      path: "/labs/admet",
      entityType: "compound",
      primaryFor: (index) => SMILES[index % SMILES.length],
      secondaryFor: () => null,
    },
    {
      module: "retrosynthesis",
      path: "/labs/retrosynthesis",
      entityType: "compound",
      primaryFor: (index) => SMILES[index % SMILES.length],
      secondaryFor: () => null,
    },
    {
      module: "molecule-generation",
      path: "/labs/molecule-generation",
      entityType: "protein",
      primaryFor: (index) => TARGET_LABELS[index % TARGET_LABELS.length],
      secondaryFor: () => null,
    },
    {
      module: "pharmacogenomics",
      path: "/labs/pharmacogenomics",
      entityType: "gene",
      primaryFor: (index) => GENES[index % GENES.length],
      secondaryFor: (index) => DISEASES[index % DISEASES.length],
    },
  ];

  const cases = [];
  for (let moduleIndex = 0; moduleIndex < modules.length; moduleIndex += 1) {
    const moduleDef = modules[moduleIndex];
    for (let variant = 0; variant < 10; variant += 1) {
      const index = moduleIndex * 10 + variant;
      cases.push({
        id: `labs-${index + 1}`,
        label: `${moduleDef.module} :: ${variant + 1}`,
        path: moduleDef.path,
        module: moduleDef.module,
        query: `${moduleDef.module} ${moduleDef.primaryFor(index)}`,
        entityType: moduleDef.entityType,
        seedName: moduleDef.primaryFor(index),
        primary: moduleDef.primaryFor(index),
        secondary: moduleDef.secondaryFor(index),
        identifiers: moduleDef.entityType === "protein" ? { pdb_id: moduleDef.primaryFor(index) } : undefined,
      });
    }
  }
  return cases;
}

function buildContradictionCases() {
  return buildCartesianCases(DISEASES, COHORTS, (disease, cohort, index) => ({
    id: `contradiction-${index + 1}`,
    label: `${disease} ${cohort}`,
    query: `${disease} ${cohort} contradictory evidence`,
    seedName: disease,
  }));
}

function buildPicoCases() {
  return buildCartesianCases(DISEASES, PATIENT_ARCHETYPES, (disease, archetype, index) => ({
    id: `pico-${index + 1}`,
    label: `${disease} ${archetype}`,
    query: `${disease} ${archetype}`,
    seedName: disease,
    abstract: `A randomized controlled trial in ${archetype} patients with ${disease} compared intervention ${index + 1} versus standard of care over 12 months. The primary outcome improved significantly with intervention ${index + 1}, while safety events remained manageable.` ,
  }));
}

function buildSettingsCases() {
  const cases = [];
  let index = 0;
  for (const tab of SETTINGS_TABS) {
    for (const check of SETTINGS_CHECKS) {
      index += 1;
      cases.push({
        id: `settings-${index}`,
        label: `${tab.label} :: ${check}`,
        tab: tab.id,
        tabLabel: tab.label,
        check,
      });
    }
  }
  return cases;
}

function buildCartesianCases(left, right, builder) {
  const cases = [];
  for (let leftIndex = 0; leftIndex < left.length; leftIndex += 1) {
    for (let rightIndex = 0; rightIndex < right.length; rightIndex += 1) {
      cases.push(builder(left[leftIndex], right[rightIndex], cases.length));
    }
  }
  return cases;
}

async function settlePage(page) {
  try {
    await page.waitForLoadState("networkidle", { timeout: 3000 });
  } catch {
    await page.waitForTimeout(600);
  }

  await page.waitForFunction(
    () => {
      const text = document.body ? (document.body.innerText || "") : "";
      const booting = text.includes("Initializing Engine");
      const hasShell = !!document.querySelector("nav[aria-label='Main navigation']") || !!document.querySelector("main") || !!document.querySelector("input, button, textarea, select");
      return hasShell && !booting;
    },
    { timeout: 10000 },
  ).catch(() => {});

  await page.waitForTimeout(400);
}

async function dismissRetry(page) {
  const retryButton = page.locator('button:has-text("Retry")').first();
  if (await retryButton.isVisible().catch(() => false)) {
    await retryButton.click().catch(() => {});
    await page.waitForTimeout(800);
  }
}

async function waitForPrimaryResponse(page, patterns, timeoutMs) {
  try {
    const response = await page.waitForResponse(
      (candidate) => patterns.some((pattern) => candidate.url().includes(pattern)),
      { timeout: timeoutMs },
    );
    return response;
  } catch {
    return null;
  }
}

async function summarizePrimaryResponse(response) {
  if (!response) {
    return { matched: false, ok: false, timedOut: true, status: null, url: null, method: null, summary: "response-timeout" };
  }

  let summary = "non-json";
  try {
    const text = await response.text();
    summary = summarizeTextPayload(text);
  } catch {
    summary = "unreadable-body";
  }

  return {
    matched: true,
    ok: response.ok(),
    timedOut: false,
    status: response.status(),
    url: trimUrl(response.url()),
    method: response.request().method(),
    summary,
  };
}

async function summarizePrimaryOutcome(page, pageDef, response, requestFailures) {
  const responseSummary = await summarizePrimaryResponse(response);
  if (responseSummary.matched) {
    return responseSummary;
  }

  if (!Array.isArray(pageDef.successTexts) || pageDef.successTexts.length === 0) {
    return responseSummary;
  }

  const hasMatchingFailure = requestFailures.some((failure) =>
    pageDef.apiPatterns.some((pattern) => failure.includes(pattern)),
  );
  if (hasMatchingFailure) {
    return responseSummary;
  }

  const mainText = await page.locator("main").innerText().catch(async () =>
    page.locator("body").innerText().catch(() => ""),
  );

  for (const text of pageDef.successTexts) {
    if (mainText.includes(text)) {
      return {
        matched: true,
        ok: true,
        timedOut: false,
        status: null,
        url: null,
        method: null,
        summary: `ui-signal:${text}`,
      };
    }
  }

  return responseSummary;
}

function summarizeTextPayload(text) {
  if (!text) return "empty-body";
  try {
    const json = JSON.parse(text);
    if (Array.isArray(json)) {
      return `array:${json.length}`;
    }
    const keys = Object.keys(json).slice(0, 8);
    const totals = [];
    if (typeof json.total === "number") totals.push(`total=${json.total}`);
    if (typeof json.status === "string") totals.push(`status=${json.status}`);
    if (typeof json.run_id === "string") totals.push(`run_id=${json.run_id}`);
    if (json.results && typeof json.results === "object") totals.push(`result_keys=${Object.keys(json.results).length}`);
    return `keys:${keys.join(",")}${totals.length ? ` :: ${totals.join(" ")}` : ""}`;
  } catch {
    return `text:${truncate(text.replace(/\s+/g, " "), 140)}`;
  }
}

async function collectPageMetrics(page) {
  return page.evaluate(() => {
    const bodyText = document.body ? document.body.innerText || "" : "";
    const mainNavCount = document.querySelectorAll("nav[aria-label='Main navigation'] a").length;
    return {
      rendered: bodyText.trim().length > 40,
      bodyTextLength: bodyText.length,
      horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
      navCount: mainNavCount,
      title: document.title,
      url: window.location.pathname + window.location.search,
      headings: Array.from(document.querySelectorAll("h1, h2")).slice(0, 4).map((node) => node.textContent?.trim() || "").filter(Boolean),
    };
  });
}

function summarizePageResults(results) {
  const summary = {
    total: results.length,
    uiRendered: results.filter((item) => item.ui?.rendered).length,
    apiMatched: results.filter((item) => item.api?.matched).length,
    apiOk: results.filter((item) => item.api?.ok).length,
    apiTimeout: results.filter((item) => item.api?.timedOut).length,
    overflowCases: results.filter((item) => item.ui?.horizontalOverflow).length,
    consoleIssueCases: results.filter((item) => (item.consoleIssues || []).length > 0).length,
    fatalCases: results.filter((item) => item.fatalError).length,
    topErrors: topCounts(results.flatMap((item) => item.consoleIssues || []).concat(results.flatMap((item) => item.requestFailures || [])), 8),
  };
  return summary;
}

function formatSummaryMarkdown(summary) {
  const lines = [];
  lines.push("# Deep Page Audit Summary");
  lines.push("");
  lines.push(`- Base URL: ${summary.baseUrl}`);
  lines.push(`- Cases per page: ${summary.queryCount}`);
  lines.push(`- Total cases: ${summary.totalCases}`);
  lines.push(`- UI rendered: ${summary.uiRendered}/${summary.totalCases}`);
  lines.push(`- Primary API matched: ${summary.apiMatched}/${summary.totalCases}`);
  lines.push(`- Primary API OK: ${summary.apiOk}/${summary.totalCases}`);
  lines.push(`- Primary API timeout/no-response: ${summary.apiTimeout}/${summary.totalCases}`);
  lines.push(`- Overflow cases: ${summary.overflowCases}`);
  lines.push(`- Cases with console issues: ${summary.consoleIssueCases}`);
  lines.push("");
  lines.push("## Per-page");
  lines.push("");
  for (const [pageId, pageSummary] of Object.entries(summary.pageSummaries)) {
    lines.push(`### ${pageId}`);
    lines.push(`- UI rendered: ${pageSummary.uiRendered}/${pageSummary.total}`);
    lines.push(`- API OK: ${pageSummary.apiOk}/${pageSummary.total}`);
    lines.push(`- API timeout: ${pageSummary.apiTimeout}/${pageSummary.total}`);
    lines.push(`- Overflow: ${pageSummary.overflowCases}`);
    lines.push(`- Fatal: ${pageSummary.fatalCases}`);
    if (pageSummary.topErrors.length) {
      lines.push(`- Top issues: ${pageSummary.topErrors.map((entry) => `${entry.count}x ${entry.value}`).join(" | ")}`);
    }
    lines.push("");
  }
  return lines.join("\n");
}

function buildHandoffPayload({ targetRoute, action, query, entityType, entityName, identifiers, metadata }) {
  return {
    version: "phase0.v1",
    sourceModule: "cockpit",
    action,
    targetRoute,
    query,
    createdAt: new Date().toISOString(),
    entities: [
      {
        entityId: slugify(entityName || query || "audit"),
        entityType,
        entityName: entityName || query,
        identifiers: identifiers || {},
        attributes: metadata || {},
      },
    ],
    provenance: [
      {
        source: "deep-page-audit",
        retrievedAt: new Date().toISOString(),
      },
    ],
    metadata: metadata || {},
  };
}

async function firstVisible(page, selectors) {
  for (const selector of selectors) {
    const locator = page.locator(selector).first();
    if (await locator.isVisible().catch(() => false)) {
      return locator;
    }
  }
  throw new Error(`No visible selector matched: ${selectors.join(", ")}`);
}

async function firstVisibleOptional(page, selectors) {
  for (const selector of selectors) {
    const locator = page.locator(selector).first();
    if (await locator.isVisible().catch(() => false)) {
      return locator;
    }
  }
  return null;
}

async function clearAndFill(locator, value) {
  await locator.click({ timeout: 2000 }).catch(() => {});
  await locator.fill("").catch(() => {});
  await locator.fill(value, { timeout: 5000 });
}

async function clickFirst(page, labels) {
  for (const label of labels) {
    const locator = page.locator(`button:has-text("${label}")`).first();
    if (await locator.isVisible().catch(() => false)) {
      await locator.scrollIntoViewIfNeeded().catch(() => {});
      if (!(await locator.isEnabled().catch(() => false))) {
        continue;
      }
      try {
        await locator.click({ timeout: 3000 });
        return true;
      } catch {
        continue;
      }
    }
  }
  return false;
}

async function pressEnterOrClick(page, locator, labels) {
  try {
    await locator.press("Enter");
    return true;
  } catch {
    return clickFirst(page, labels);
  }
}

async function locatorPressEnter(locator) {
  try {
    await locator.press("Enter");
    return true;
  } catch {
    return false;
  }
}

async function clickTab(page, label) {
  const button = page.locator(`button:has-text("${label}")`).first();
  if (await button.isVisible().catch(() => false)) {
    await button.click().catch(() => {});
  }
}

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function appendJsonLine(filePath, value) {
  fs.appendFileSync(filePath, `${JSON.stringify(value)}\n`, "utf8");
}

function topCounts(values, limit) {
  const counts = new Map();
  for (const value of values.filter(Boolean)) {
    counts.set(value, (counts.get(value) || 0) + 1);
  }
  return Array.from(counts.entries())
    .sort((left, right) => right[1] - left[1])
    .slice(0, limit)
    .map(([value, count]) => ({ value, count }));
}

function uniqueFirst(values, limit) {
  return Array.from(new Set(values)).slice(0, limit);
}

function shouldIgnoreConsoleIssue(text) {
  return text.includes("fonts.gstatic.com") && text.includes("preloaded using link preload but not used");
}

function shouldIgnoreRequestFailure(text) {
  return text.includes("/api/health") && text.includes("net::ERR_ABORTED");
}

function slugify(value) {
  return String(value || "audit")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60) || "audit";
}

function trimUrl(url) {
  return url.replace(BASE_URL, "").replace("http://127.0.0.1:8000", "").replace("http://localhost:8000", "");
}

function truncate(value, length) {
  if (value.length <= length) return value;
  return `${value.slice(0, length - 3)}...`;
}

function timestampSlug() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});